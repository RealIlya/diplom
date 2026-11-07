"""Native KEV feature extraction and frozen/CE/Brier head-only comparison."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import random
import time
import traceback
from .data import digest,write_json
from .compare import filehash,quality,request_payload


def hard(row):return row['label'] in {'useful','irrelevant'} and not row.get('defect',False)


def head_loss(logits,labels,loss):
    import torch
    if loss=='ce':return torch.nn.functional.cross_entropy(logits,labels)
    if loss=='brier':return ((torch.softmax(logits,-1)[:,1]-labels.float())**2).mean()
    raise ValueError('unknown loss')


def probability(logits,temperature):
    z=(logits[1]-logits[0])/temperature
    if z>=0:return 1/(1+math.exp(-z))
    e=math.exp(z);return e/(1+e)


def fit_temperature(logits,rows,candidates):
    selected=[r for r in rows if r['role']=='calibration' and hard(r) and r['id'] in logits]
    if not selected:raise ValueError('no calibration data')
    if not all(math.isfinite(t) and t>0 for t in candidates):raise ValueError('invalid temperature')
    return min(candidates,key=lambda t:quality([int(r['label']=='useful') for r in selected],
        [probability(logits[r['id']],t) for r in selected])['nll'])


def train_one(head,rows,features,loss,config):
    import torch
    train=[r for r in rows if r['role']=='train' and hard(r) and r['id'] in features]
    if not train:raise ValueError('no hard train features')
    head.train();optimizer=torch.optim.AdamW(head.parameters(),lr=config['lr'],weight_decay=config['weight_decay'])
    rng=random.Random(config['seed']);curves=[]
    for epoch in range(config['epochs']):
        order=list(train);rng.shuffle(order);total=0.
        for start in range(0,len(order),config['batch_size']):
            batch=order[start:start+config['batch_size']]
            z=torch.stack([head(*features[r['id']]) for r in batch])
            labels=torch.tensor([int(r['label']=='useful') for r in batch],dtype=torch.long)
            value=head_loss(z,labels,loss)
            if not torch.isfinite(value):raise ValueError('nonfinite training loss')
            optimizer.zero_grad();value.backward();optimizer.step();total+=float(value.detach())*len(batch)
        curves.append({'epoch':epoch+1,'loss':total/len(train),'train_rows':len(train)})
    return curves


def predict(head,rows,features):
    import torch
    head.eval();head.temperature=1.
    logits={};errors={}
    with torch.inference_mode():
        for row in rows:
            rid=row['id']
            if rid not in features:errors[rid]='missing native features';continue
            z=head(*features[rid]).tolist()
            if len(z)!=2 or not all(math.isfinite(v) for v in z):errors[rid]='invalid logits';continue
            logits[rid]=z
    return logits,errors


def load_dataset(folder,protocol):
    manifest=json.loads((folder/'manifest.json').read_text())
    if not manifest['gates_passed']:raise ValueError('dataset gates failed')
    if manifest['dataset_sha256']!=filehash(folder/'dataset.jsonl') or manifest['protocol_sha256']!=filehash(protocol):
        raise ValueError('dataset/protocol changed')
    return [json.loads(s) for s in (folder/'dataset.jsonl').read_text().splitlines()]


def features(args):
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    import torch
    from .compare import Kev,memory
    from .live_api import utc
    rows=load_dataset(args.dataset,args.protocol);protocol=json.loads(args.protocol.read_text())
    args.out.mkdir(parents=True,exist_ok=False)
    receipt={'started_at':utc(),'status':'running','dataset_sha256':filehash(args.dataset/'dataset.jsonl'),
             'protocol_sha256':filehash(args.protocol),'code_sha256':filehash(Path(__file__)),'feature_labels_in_input':False}
    stream=(args.out/'index.jsonl').open('x')
    try:
        start=time.perf_counter();adapter=Kev(protocol['model']['arm']);adapter.sync()
        receipt.update(load_seconds=time.perf_counter()-start,dtype=adapter.dtype,published_temperature=adapter.temperature,
                       head_dim=adapter.model.head.q.weight.shape[0],hidden_dim=adapter.model.head.q.weight.shape[1],
                       weights_receipts=adapter.weights_receipts,memory_after_load=memory('mlx'))
        torch.save(copy.deepcopy(adapter.model.head.state_dict()),args.out/'original-head.pt')
        receipt['original_head_sha256']=filehash(args.out/'original-head.pt')
        write_json(args.out/'receipt-start.json',receipt)
        captured=[]
        def capture(module,inputs):captured.append(tuple(x.detach().cpu().clone() for x in inputs))
        hook=adapter.model.head.register_forward_pre_hook(capture)
        for row in rows:
            record={'row_id':row['id'],'input_sha256':digest(row['input']),'semantic_sha256':digest(request_payload(row))}
            try:
                adapter.sync();start=time.perf_counter();enc,ids=adapter.encode(row);tokenized=time.perf_counter()
                captured.clear();p,z=adapter.forward(enc);adapter.sync();end=time.perf_counter()
                if len(captured)!=1:raise ValueError('expected one native head invocation')
                h,opts=captured[0]
                if h.ndim!=1 or tuple(opts.shape)!=(2,h.shape[0]) or not torch.isfinite(h).all() or not torch.isfinite(opts).all():
                    raise ValueError('invalid native head features')
                target=args.out/(row['id']+'.pt');torch.save({'h':h,'opts':opts},target)
                record.update(status='ok',feature_file=target.name,feature_sha256=filehash(target),
                              native_probability=p,native_logits=z,full_tokens=len(ids),ids_sha256=digest(ids),
                              tokenize_seconds=tokenized-start,request_seconds=end-start)
            except Exception as exc:record.update(status='error',error=repr(exc),traceback=traceback.format_exc())
            stream.write(json.dumps(record)+'\n');stream.flush();print(json.dumps({k:record.get(k) for k in ['row_id','status','request_seconds','error']}),flush=True)
        hook.remove();receipt['status']='completed';receipt['memory_final']=memory('mlx');receipt['index_sha256']=filehash(args.out/'index.jsonl')
    except Exception as exc:
        receipt.update(status='failed',error=repr(exc),traceback=traceback.format_exc());raise
    finally:
        receipt['finished_at']=utc();write_json(args.out/'receipt.json',receipt);stream.close()


def train(args):
    import torch
    from .compare import ASSETS
    from .live_api import utc
    import sys
    sys.path.insert(0,str(ASSETS/'kev-2ecafc49fe1e8945cd600443e6c04c1cf0b3a78f'))
    from kev.model import PointerHead
    rows=load_dataset(args.dataset,args.protocol);p=json.loads(args.protocol.read_text());config=p['training']
    receipt=json.loads((args.cache/'receipt.json').read_text())
    if receipt['status']!='completed' or receipt['dataset_sha256']!=filehash(args.dataset/'dataset.jsonl') or receipt['protocol_sha256']!=filehash(args.protocol):
        raise ValueError('feature cache differs from dataset/protocol')
    if filehash(args.cache/'original-head.pt')!=receipt['original_head_sha256'] or filehash(args.cache/'index.jsonl')!=receipt['index_sha256']:
        raise ValueError('feature index/head changed')
    features_by_id={};native={}
    for record in (json.loads(s) for s in (args.cache/'index.jsonl').read_text().splitlines()):
        if record['status']!='ok':continue
        target=args.cache/record['feature_file']
        if filehash(target)!=record['feature_sha256']:raise ValueError('feature bytes changed')
        row=next(r for r in rows if r['id']==record['row_id'])
        if digest(row['input'])!=record['input_sha256']:raise ValueError('cache input changed')
        f=torch.load(target,map_location='cpu',weights_only=True);features_by_id[row['id']]=(f['h'],f['opts']);native[row['id']]=record['native_probability']
    # Cache failures are not labels, and must not erase a required role/class.
    for role in ['train','calibration','validation']:
        admitted=[r for r in rows if r['role']==role and hard(r) and r['id'] in features_by_id]
        if {r['label'] for r in admitted}!={'useful','irrelevant'}:raise ValueError('cache lost role/class coverage')
        gates=p['gates']
        if len({r['family'] for r in admitted})<gates[role+'_families_min'] or len(admitted)<gates.get(role+'_hard_min',1):
            raise ValueError('cache lost required sample coverage')
    args.out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(4)
    initial=torch.load(args.cache/'original-head.pt',map_location='cpu',weights_only=True)
    summary={'started_at':utc(),'protocol_sha256':filehash(args.protocol),'dataset_sha256':filehash(args.dataset/'dataset.jsonl'),
             'feature_receipt_sha256':filehash(args.cache/'receipt.json'),'training':config,'arms':{},'test_used':False}
    all_predictions=[]
    for arm in ['frozen']+config['losses']:
        torch.manual_seed(config['seed']);head=PointerHead(receipt['hidden_dim'],dp=receipt['head_dim']);head.load_state_dict(initial)
        start=time.perf_counter();curves=[]
        if arm!='frozen':curves=train_one(head,rows,features_by_id,arm,config)
        logits,errors=predict(head,rows,features_by_id)
        t=fit_temperature(logits,rows,config['temperature_grid'])
        temperatures={'published':receipt['published_temperature'],'calibrated':t}
        a={'train_seconds':time.perf_counter()-start,'curves':curves,'temperatures':temperatures,'errors':errors,'metrics':{}}
        for mode,temperature in temperatures.items():
            for role in ['train','calibration','validation']:
                hard_rows=[r for r in rows if r['role']==role and hard(r) and r['id'] in logits]
                probs=[probability(logits[r['id']],temperature) for r in hard_rows];labels=[int(r['label']=='useful') for r in hard_rows]
                metrics=quality(labels,probs);families={}
                for family in sorted({r['family'] for r in hard_rows}):
                    subset=[r for r in hard_rows if r['family']==family]
                    families[family]=quality([int(r['label']=='useful') for r in subset],[probability(logits[r['id']],temperature) for r in subset])
                metrics['family_accuracy_macro']=sum(v['accuracy'] for v in families.values())/len(families)
                metrics['families']=families;a['metrics'][mode+'/'+role]=metrics
            for row in rows:
                if row['id'] in logits:all_predictions.append({'arm':arm,'mode':mode,'role':row['role'],'row_id':row['id'],
                    'label':row['label'],'probability':probability(logits[row['id']],temperature),'temperature':temperature})
        if arm=='frozen':
            max_delta=max(abs(probability(logits[rid],receipt['published_temperature'])-value) for rid,value in native.items())
            a['native_probability_max_delta']=max_delta
            if max_delta>1e-6:raise ValueError('cached head differs from native inference')
        torch.save({'head':head.state_dict(),'temperature':t,'original_temperature':receipt['published_temperature'],
                    'base_checkpoint_revision':p['model']['checkpoint_revision'],'hidden_dim':receipt['hidden_dim'],'head_dim':receipt['head_dim'],
                    'protocol_sha256':filehash(args.protocol),'dataset_sha256':filehash(args.dataset/'dataset.jsonl'),'arm':arm},args.out/(arm+'.pt'))
        summary['arms'][arm]=a;print(json.dumps({'arm':arm,'temperature':t,'validation':a['metrics']['calibrated/validation']}),flush=True)
    with (args.out/'predictions.jsonl').open('x') as f:
        for r in all_predictions:f.write(json.dumps(r)+'\n')
    summary['finished_at']=utc();write_json(args.out/'summary.json',summary)


def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(required=True)
    for name,func in [('features',features),('train',train)]:
        a=s.add_parser(name);a.add_argument('--protocol',type=Path,required=True);a.add_argument('--dataset',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
        if name=='train':a.add_argument('--cache',type=Path,required=True)
        a.set_defaults(func=func)
    a=p.parse_args();a.func(a)

if __name__=='__main__':main()
