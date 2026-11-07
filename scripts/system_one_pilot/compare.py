"""Frozen local inference comparison; no collection, annotation or fitting."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import subprocess
import sys
import time
import traceback
from .data import digest, bm25, write_json
from .model import QUESTION, input_text, binary_metrics

ROOT=Path(__file__).resolve().parents[2]
RESULT=ROOT/'experiments/system-one-pilot/results/kev-comparison-20261025'
ASSETS=ROOT/'artifacts/system-one-pilot/kev-comparison-v1'
PROTOCOL=RESULT/'protocol.json'


def filehash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
    return h.hexdigest()


def verify_weights(path,repo,revision):
    receipt=json.loads(Path(path).read_text())
    if receipt['repo']!=repo or receipt['revision']!=revision:raise ValueError('weights revision differs')
    for f in receipt['files']:
        p=ROOT/f['path']
        if p.stat().st_size!=f['bytes'] or filehash(p)!=f['sha256']:raise ValueError('weights bytes differ')
    return filehash(path)


def validate_run(cards,receipt,records,protocol):
    if receipt['status']=='running':raise ValueError('run still running')
    if receipt['protocol_sha256']!=filehash(PROTOCOL):raise ValueError('run protocol differs')
    if receipt['cohort_sha256']!=protocol['cohort_sha256']:raise ValueError('run cohort differs')
    ids={c['id'] for c in cards};seen=set()
    for r in records:
        key=(r['phase'],r['row_id'],r.get('repeat'))
        if r['row_id'] not in ids or key in seen:raise ValueError('unknown or duplicate record')
        seen.add(key)
    if receipt['status']=='completed':
        admission=[r for r in records if r['phase']=='admission']
        if len(admission)!=len(cards):raise ValueError('incomplete admission')
        for r in admission:
            if r['status']=='ok' and any(('measure',r['row_id'],i) not in seen for i in range(protocol['performance_repeats'])):
                raise ValueError('incomplete repetitions')


def load_cohort(path, protocol):
    if filehash(path)!=protocol['cohort_sha256']:raise ValueError('cohort hash differs')
    records=[json.loads(s) for s in Path(path).read_text().splitlines()]
    cards=[];seen=set()
    for r in records:
        rid=r['row_id']; c=r['card']; label=r['decision']['label']
        if rid in seen:raise ValueError('duplicate row')
        seen.add(rid)
        if c['id']!=rid or digest(c['input'])!=r['input_sha256']:raise ValueError('input changed')
        if label not in {'useful','irrelevant','uncertain'}:raise ValueError('invalid label')
        cards.append(dict(c,label=label))
    if len(cards)!=protocol['rows'] or sum(c['label']!='uncertain' for c in cards)!=protocol['hard_labels']:
        raise ValueError('cohort counts differ')
    if len({c['family'] for c in cards})!=protocol['families']:raise ValueError('family count differs')
    return cards


def request_payload(card):
    return {'state':input_text(card),'questions':{'useful':dict(QUESTION)}}


def quality(labels, probabilities):
    if any(y not in (0,1) for y in labels):raise ValueError('invalid label')
    m=binary_metrics(labels,probabilities)
    tp=sum(y==1 and p>=.5 for y,p in zip(labels,probabilities))
    tn=sum(y==0 and p<.5 for y,p in zip(labels,probabilities))
    fp=sum(y==0 and p>=.5 for y,p in zip(labels,probabilities))
    fn=sum(y==1 and p<.5 for y,p in zip(labels,probabilities))
    pos=[p for y,p in zip(labels,probabilities) if y];neg=[p for y,p in zip(labels,probabilities) if not y]
    m.update(f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
             balanced_accuracy=(tp/(tp+fn)+tn/(tn+fp))/2 if pos and neg else None,
             roc_auc=sum((p>n)+.5*(p==n) for p in pos for n in neg)/(len(pos)*len(neg)) if pos and neg else None,
             tp=tp,tn=tn,fp=fp,fn=fn)
    return m


def arm_quality(cards,records):
    predictions={}
    for r in records:
        if r.get('phase')!='measure' or r.get('repeat')!=0:continue
        if r['row_id'] in predictions:raise ValueError('duplicate first prediction')
        if r['status']=='ok':
            p=r['probability']
            if not math.isfinite(p) or not 0<=p<=1:raise ValueError('invalid probability')
            predictions[r['row_id']]=p
    hard=[c for c in cards if c['label']!='uncertain' and c['id'] in predictions]
    return {'coverage':len(predictions)/len(cards),'predicted':len(predictions),'predictions':predictions,
            'quality':quality([int(c['label']=='useful') for c in hard],[predictions[c['id']] for c in hard]) if hard else None}


def common_ids(arms):
    return sorted(set.intersection(*(set(a['predictions']) for a in arms.values())))


def percentile(values,q):
    if not values:return None
    v=sorted(values);i=(len(v)-1)*q;lo=int(i);hi=min(lo+1,len(v)-1)
    return v[lo]+(v[hi]-v[lo])*(i-lo)


def swap():
    return subprocess.check_output(['/usr/sbin/sysctl','vm.swapusage'],text=True).strip()


def memory(backend):
    import psutil
    m={'rss_bytes':psutil.Process().memory_info().rss,
       'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    if backend=='mlx':
        import mlx.core as mx
        m.update(mlx_active_bytes=mx.get_active_memory(),mlx_cache_bytes=mx.get_cache_memory(),mlx_peak_bytes=mx.get_peak_memory())
    else:
        import torch
        m.update(mps_current_bytes=torch.mps.current_allocated_memory(),mps_driver_bytes=torch.mps.driver_allocated_memory())
    return m


class Laya:
    backend='mps'
    def __init__(self):
        from .live import verify_checkpoint, LAYA, CHECKPOINT
        from .model import runtime
        verify_checkpoint()
        self.torch,self.model,self.tok,cfg=runtime(LAYA,CHECKPOINT)
        self.torch.set_num_threads(4)
        if not self.torch.backends.mps.is_available():raise RuntimeError('MPS unavailable')
        self.device=self.torch.device('mps');self.model.to(self.device).eval()
        self.temperature=float(cfg.get('temperature_by_options',{}).get('noul:2',cfg['temperature'][2]))
        self.dtype=str(next(self.model.parameters()).dtype)
    def encode(self,card):
        from .model import admit
        from laya.train import to_internal, make_item, encode_item
        from laya.common import collate_items,state_room
        q=to_internal('useful',QUESTION)
        ids=admit(self.tok,input_text(card),state_room(self.tok,q,4096,256))
        item,error=make_item(self.tok,q,[.5,.5],ids,256,4096)
        if error:raise ValueError(error)
        batch=collate_items([[encode_item(self.tok,item,4096,256)]],self.tok.pad_token_id)
        actual=batch['input_ids'][0].tolist()
        if card.get('scorer_input_ids') is not None and actual!=card['scorer_input_ids']:raise ValueError('stored serializer differs')
        return batch,actual
    def sync(self):self.torch.mps.synchronize()
    def forward(self,enc):
        from laya.train import _forward
        with self.torch.inference_mode():
            logits=_forward(self.model,enc,self.device,False,True)[0]
            p=float(self.torch.softmax(logits/self.temperature,-1)[1].cpu())
        return p,logits.cpu().tolist()


class Kev:
    backend='mlx'
    def __init__(self,arm):
        sys.path.insert(0,str(ASSETS/'kev-2ecafc49fe1e8945cd600443e6c04c1cf0b3a78f'))
        import torch
        import mlx.core as mx
        from kev.checkpoint import Checkpoint
        from kev.model import pad_id,is_hybrid
        from kev.mlx_model import load_base,merge_lora,MLXDecisionModel
        from transformers import AutoTokenizer,AutoConfig
        self.torch=torch;self.mx=mx;torch.set_num_threads(4)
        size='0.8B' if arm=='kev-0.8b' else '4B'
        base=ASSETS/'checkpoints'/('Qwen--Qwen3.5-'+size+'-Base')
        meta=json.loads((ASSETS/('Qwen--Qwen3.5-'+size+'-Base-metadata.json')).read_text())
        protocol=json.loads(PROTOCOL.read_text())
        self.weights_receipts=[verify_weights(ASSETS/('Qwen--Qwen3.5-'+size+'-Base-verified.json'),meta['id'],meta['sha']),
                              verify_weights(ASSETS/('jaredpalmer--'+arm+'-verified.json'),'jaredpalmer/'+arm,protocol['models'][arm])]
        ck=Checkpoint(str((ASSETS/'checkpoints'/('jaredpalmer--'+arm)).resolve()))
        meta=json.loads((ASSETS/('Qwen--Qwen3.5-'+size+'-Base-metadata.json')).read_text())
        if ck.meta.base!=meta['id'] or ck.meta.base_revision!=meta['sha']:raise ValueError('base pin differs')
        if ck.full or ck.meta.option_isolation or ck.meta.special_embeddings or ck.adapter_config().get('trainable_token_indices'):
            raise ValueError('unsupported checkpoint flags')
        cfg=AutoConfig.from_pretrained(base,local_files_only=True)
        if not is_hybrid(cfg.get_text_config()):raise ValueError('not hybrid')
        self.tok=AutoTokenizer.from_pretrained(base,local_files_only=True)
        lm=load_base(str(base.resolve()));self.merged=merge_lora(lm,ck.path,scale=1.)
        self.model=MLXDecisionModel(lm,pad_id(self.tok),head_dim=ck.meta.head_dim)
        self.model.head.load_state_dict(ck.meta.head);self.model.eval()
        self.temperature=float(ck.meta.temperature);self.model.head.temperature=self.temperature
        self.dtype=self.model.dtype+' + CPU head float32'
    def encode(self,card):
        from kev.api import SystemOneRequest,to_record
        rec,_=to_record(SystemOneRequest(**request_payload(card)))
        enc=self.model.encode(self.tok,rec,strict=True,max_state=8192,max_branch=8192)
        if enc['state_truncated']:raise ValueError('state truncated')
        return enc,enc['ids']
    def sync(self):self.mx.synchronize()
    def forward(self,enc):
        logits=self.model.forward(enc)[0]
        return float(self.torch.softmax(logits,-1)[1]),logits.tolist()


def run(args):
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',TOKENIZERS_PARALLELISM='false')
    protocol=json.loads(PROTOCOL.read_text());cards=load_cohort(ROOT/protocol['cohort_source'],protocol)
    args.out.mkdir(parents=True,exist_ok=False)
    receipt={'arm':args.arm,'status':'running','started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
             'cohort_sha256':protocol['cohort_sha256'],'protocol_sha256':filehash(PROTOCOL),'runner_sha256':filehash(Path(__file__)),
             'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),
             'command':sys.argv,'memory_limitations':'MPS backend peak unavailable in public API; report max post-request samples separately. Process peak RSS includes load; unified allocator and RSS overlap.', 'swap_before':swap(),'external_inference_calls':0,'training':False}
    stream=(args.out/'records.jsonl').open('x')
    def emit(r):stream.write(json.dumps(r,ensure_ascii=False)+'\n');stream.flush()
    try:
        receipt['versions']={n:importlib.metadata.version(n) for n in ['torch','transformers','numpy','psutil']}
        if args.arm!='laya':receipt['versions'].update({n:importlib.metadata.version(n) for n in ['mlx','mlx-lm','peft']})
        start=time.perf_counter();adapter=Laya() if args.arm=='laya' else Kev(args.arm);adapter.sync()
        receipt.update(load_seconds=time.perf_counter()-start,backend=adapter.backend,dtype=adapter.dtype,
                       temperature=adapter.temperature,memory_after_load=memory(adapter.backend))
        receipt['weights_receipt_sha256']=getattr(adapter,'weights_receipts',None)
        write_json(args.out/'receipt-start.json',receipt)
        if adapter.backend=='mlx':adapter.mx.reset_peak_memory()
        admitted=[]
        for c in cards:
            try:
                enc,ids=adapter.encode(c)
                admitted.append((len(ids),c))
                emit({'phase':'admission','row_id':c['id'],'status':'ok','tokens':len(ids),'ids':ids,
                      'ids_sha256':digest(ids),'semantic_sha256':digest(request_payload(c))})
            except Exception as exc:
                emit({'phase':'admission','row_id':c['id'],'status':'error','error':repr(exc),'traceback':traceback.format_exc()})
        if not admitted:raise ValueError('no admitted rows')
        ordered=sorted(admitted,key=lambda x:(x[0],x[1]['id']))
        warm=[ordered[i][1] for i in [0,len(ordered)//2,len(ordered)-1]]
        # One seeded order fixed for all arms; admission differences only filter it.
        order=list(cards);random.Random(protocol['order_seed']).shuffle(order)
        allowed={c['id'] for _,c in admitted};order=[c for c in order if c['id'] in allowed]
        def infer(c,phase,repeat):
            adapter.sync();start=time.perf_counter()
            record={'phase':phase,'repeat':repeat,'row_id':c['id']}
            try:
                enc,ids=adapter.encode(c);tokenized=time.perf_counter()
                adapter.sync();forward_start=time.perf_counter();p,logits=adapter.forward(enc);adapter.sync();end=time.perf_counter()
                if not math.isfinite(p) or not 0<=p<=1:raise ValueError('invalid probability')
                record.update(status='ok',probability=p,logits=logits,tokenize_seconds=tokenized-start,
                              forward_seconds=end-forward_start,request_seconds=end-start,tokens=len(ids),**memory(adapter.backend))
            except Exception as exc:
                record.update(status='error',error=repr(exc),traceback=traceback.format_exc(),elapsed_seconds=time.perf_counter()-start)
            emit(record);print(json.dumps({k:record.get(k) for k in ['phase','repeat','row_id','status','request_seconds','error']}),flush=True)
        for i,c in enumerate(warm):infer(c,'warmup',i)
        receipt['memory_after_warmup']=memory(adapter.backend)
        if adapter.backend=='mlx':adapter.mx.reset_peak_memory()
        for repeat in range(protocol['performance_repeats']):
            for c in order:infer(c,'measure',repeat)
        receipt['status']='completed'
        receipt['memory_final']=memory(adapter.backend)
    except Exception as exc:
        receipt.update(status='failed',error=repr(exc),traceback=traceback.format_exc())
        raise
    finally:
        receipt['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
        receipt['swap_after']=swap();write_json(args.out/'receipt.json',receipt);stream.close()


def prepare(args):
    p=json.loads(PROTOCOL.read_text());cards=load_cohort(ROOT/p['cohort_source'],p)
    write_json(args.out,{'cohort_sha256':p['cohort_sha256'],'rows':len(cards),'hard_labels':sum(c['label']!='uncertain' for c in cards),
                         'semantic_hashes':{c['id']:digest(request_payload(c)) for c in cards}})


def summarize(args):
    p=json.loads(PROTOCOL.read_text());cards=load_cohort(ROOT/p['cohort_source'],p)
    arms={};raw={}
    for folder in args.runs:
        receipt=json.loads((folder/'receipt.json').read_text());records=[json.loads(s) for s in (folder/'records.jsonl').read_text().splitlines()]
        validate_run(cards,receipt,records,p)
        a=arm_quality(cards,records);ok=[r for r in records if r['phase']=='measure' and r['status']=='ok']
        a.update(receipt=receipt,run=str(folder.resolve().relative_to(ROOT)),successful_requests=len(ok),
                 errors=[r for r in records if r['status']!='ok'],
                 latency={k:{'median':statistics.median([r[k] for r in ok]),'p95':percentile([r[k] for r in ok],.95)} for k in ['tokenize_seconds','forward_seconds','request_seconds']} if ok else {},
                 probability_range={c['id']:max(v)-min(v) for c in cards if (v:=[r['probability'] for r in ok if r['row_id']==c['id']])})
        arm=receipt['arm']
        if arm in arms:raise ValueError('duplicate arm')
        arms[arm]=a;raw[arm]=ok
    common=common_ids(arms);hard=[c for c in cards if c['id'] in common and c['label']!='uncertain']
    for arm,a in arms.items():
        a['common_quality']=quality([int(c['label']=='useful') for c in hard],[a['predictions'][c['id']] for c in hard]) if hard else None
        common_ok=[r for r in raw[arm] if r['row_id'] in common]
        a['common_latency']={k:{'median':statistics.median([r[k] for r in common_ok]),'p95':percentile([r[k] for r in common_ok],.95)} for k in ['tokenize_seconds','forward_seconds','request_seconds']} if common_ok else {}
        a['memory_max_post_request']={k:max(r[k] for r in raw[arm] if k in r) for k in ['rss_bytes','peak_rss_bytes','mps_current_bytes','mps_driver_bytes','mlx_active_bytes','mlx_cache_bytes','mlx_peak_bytes'] if any(k in r for r in raw[arm])}
    labeled=[c for c in cards if c['label']!='uncertain'];labels=[int(c['label']=='useful') for c in labeled]
    # BM25 ranking within each observed snapshot, retaining uncertain documents in its IDF pool.
    pools={}
    for c in cards:pools.setdefault(c['snapshot_id'],[]).append(c)
    scores={}
    for pool in pools.values():
        vals=bm25(pool[0]['input']['state'],[c['input']['candidate'] for c in pool])
        scores.update({c['id']:s for c,s in zip(pool,vals)})
    pos=[scores[c['id']] for c in labeled if c['label']=='useful'];neg=[scores[c['id']] for c in labeled if c['label']=='irrelevant']
    pairs=[]
    for pool in pools.values():
        pp=[scores[c['id']] for c in pool if c['label']=='useful'];nn=[scores[c['id']] for c in pool if c['label']=='irrelevant']
        pairs += [(x>y)+.5*(x==y) for x in pp for y in nn]
    summary={'protocol_sha256':filehash(PROTOCOL),'cohort_sha256':p['cohort_sha256'],'arms':arms,'common_ids':common,
             'common_hard_n':len(hard),'always_irrelevant':quality(labels,[0.]*len(labels)),
             'always_irrelevant_common':quality([int(c['label']=='useful') for c in hard],[0.]*len(hard)) if hard else None,
             'bm25':{'scores':scores,'pool':'within snapshot, all candidates including uncertain; pair-weighted within-pool AUC, ties=0.5',
                     'pools':len(pools),'within_pool_pairs':len(pairs),'within_pool_auc':sum(pairs)/len(pairs) if pairs else None,
                     'cross_pool_descriptive_auc':sum((x>y)+.5*(x==y) for x in pos for y in neg)/(len(pos)*len(neg))}}
    write_json(args.out,summary)


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(required=True)
    s=sub.add_parser('prepare');s.add_argument('--out',type=Path,required=True);s.set_defaults(func=prepare)
    s=sub.add_parser('run');s.add_argument('--arm',choices=['laya','kev-0.8b','kev-4b'],required=True);s.add_argument('--out',type=Path,required=True);s.set_defaults(func=run)
    s=sub.add_parser('summarize');s.add_argument('--runs',nargs='+',type=Path,required=True);s.add_argument('--out',type=Path,required=True);s.set_defaults(func=summarize)
    args=p.parse_args();args.func(args)

if __name__=='__main__':main()
