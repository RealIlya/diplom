"""Native API pilot. Run `python -m scripts.system_one_pilot.live --help`."""
import argparse
import collections
from contextlib import contextmanager
import importlib.metadata
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import resource
import sys
import time
import zipfile

from .cli import filehash
from .data import digest, write_json, KB_TOOLS, validate_rows
from .live_api import ROOT, DEEPSEEK, QWEN, PROFILES, PaidClient, BudgetError, dumps, utc, connect, preflight
from .live_data import observed_state, structural_parts, select_cards, validate_annotation, REPRESENTATION, ANNOTATION_SCHEMA
from .model import QUESTION, input_text
from .fetch import verify_file

BASE = ROOT/'artifacts/system-one-pilot'
TAU = BASE/'source/tau2-bench-4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699'
LAYA = BASE/'source/laya-68804629e8ccd9d616d48a40e87de9fabbeae069'
CHECKPOINT = ROOT/'models/laya-multilingual-1720e3e'
SPLIT = ROOT/'experiments/system-one-pilot/manifests-v3/split.json'
DEFAULT_RUN = BASE/'api-v1'
BUDGET_DB = BASE/'authorized-series-20261025.sqlite3'
RUBRIC = Path(__file__).with_name('rubric-v1.txt')


def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def save_jsonl(path, rows):
    with Path(path).open('x') as f:
        for row in rows:
            f.write(dumps(row)+'\n')


def sealed_train_tasks(tau):
    manifest = json.loads(SPLIT.read_text())
    if digest({k:v for k,v in manifest.items() if k!='manifest_sha256'}) != manifest['manifest_sha256']:
        raise ValueError('split manifest hash mismatch')
    source = json.loads(SPLIT.with_name('source-manifest.json').read_text())
    for name,sha in source['files'].items():
        if '/tasks/' in name:continue  # Task bodies are checked only for selected train IDs below.
        if filehash(tau/name) != sha:
            raise ValueError('pinned source changed: '+name)
    # Inspect only selected train task bodies. Test stays out of the collector.
    eligible = sorted((t for t,v in manifest['tasks'].items() if v['split']=='train'),
                      key=lambda t:digest([25,manifest['tasks'][t]['family'],t]))
    selected, families = [],set()
    for task_id in eligible:
        family = manifest['tasks'][task_id]['family']
        if family in families: continue
        path = tau/'data/tau2/domains/banking_knowledge/tasks'/f'{task_id}.json'
        if digest(json.loads(path.read_text())) != manifest['task_hashes'][task_id]:
            raise ValueError('selected train task hash mismatch')
        selected.append(task_id);families.add(family)
        if len(selected)==5: break
    return selected


def code_manifest():
    files={str(p.relative_to(ROOT)):p for p in Path(__file__).parent.glob('*') if p.is_file()}
    hashes={name:filehash(p) for name,p in files.items()}
    bundle=BASE/'code-snapshots'/(digest(hashes)+'.zip')
    bundle.parent.mkdir(exist_ok=True)
    if not bundle.exists():
        with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,path in files.items():archive.write(path,name)
    versions={}
    for name in ['torch','transformers','litellm','rank-bm25','certifi']:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    return {'at':utc(), 'python':sys.version, 'platform':platform.platform(),
            'source_sha256':hashes,'source_bundle':str(bundle.relative_to(ROOT)),
            'source_bundle_sha256':filehash(bundle),
            'versions':versions}


@contextmanager
def native_transport(client, episode, allow_judge=False):
    import tau2.utils.llm_utils as llm
    from litellm import ModelResponse
    original = llm.completion
    cost_original = llm.get_response_cost
    judge_class=judge_original=None
    if allow_judge:
        from tau2.evaluator.evaluator_nl_assertions import NLAssertionsEvaluator
        judge_class=NLAssertionsEvaluator
        judge_original=judge_class.__dict__['evaluate_nl_assertions']
        def checked_assertions(cls,trajectory,nl_assertions):
            checks=judge_original.__func__(cls,trajectory,nl_assertions)
            if collections.Counter(c.nl_assertion for c in checks)!=collections.Counter(nl_assertions):
                raise ValueError('judge assertion coverage differs from required assertions')
            return checks
        judge_class.evaluate_nl_assertions=classmethod(checked_assertions)
    counter = 0
    def completion(model, messages, tools=None, tool_choice=None, **kwargs):
        nonlocal counter
        requested_role=kwargs.pop('pilot_role',None)
        role='agent' if requested_role=='agent' else ('judge' if allow_judge and model!=DEEPSEEK else 'simulator')
        payload = {'model':DEEPSEEK, 'messages':messages, 'max_tokens':2048,
                   'temperature':0, 'reasoning':{'effort':'low'} if role in {'agent','judge'} else {'enabled':False}}
        if role=='judge':payload['response_format']={'type':'json_object'}
        if tools:
            payload.update(tools=tools,tool_choice=tool_choice or 'auto')
        call_id = f'{episode}/{counter:03}/{role}'
        counter += 1
        raw = client.complete(call_id,payload)
        if raw['choices'][0].get('finish_reason') not in {'stop','tool_calls'}:
            raise ValueError('native response incomplete')
        print(dumps({'call':call_id,'usage':raw.get('usage'),'provider':raw.get('provider')}),flush=True)
        return ModelResponse(**raw)
    llm.completion = completion
    llm.get_response_cost = lambda r:float((r.get('usage') or {}).get('cost') or 0)
    try:
        yield
    finally:
        llm.completion = original
        llm.get_response_cost = cost_original
        if judge_class is not None:judge_class.evaluate_nl_assertions=judge_original


def collect(args):
    args.root.mkdir(parents=True,exist_ok=True)
    plan_path = args.root/'collection-plan.json'
    if getattr(args,'plan',None):
        from .adaptation import verify_collection_plan
        plan=verify_collection_plan(args.plan)
        selected=plan['tasks']
    else:
        selected=sealed_train_tasks(TAU)
        plan = {'version':1,'tasks':selected,'split_sha256':filehash(SPLIT),
            'max_steps':80,'max_errors':5,'timeout':900,'seed':25,
            'agent':DEEPSEEK,'simulator':DEEPSEEK,'retrieval':'bm25',
            'full_native_reward':'not measured; native ENV evaluator only'}
    if plan_path.exists():
        if json.loads(plan_path.read_text())!=plan: raise ValueError('collection plan changed')
    else: write_json(plan_path,plan)
    facts = preflight(args.root/'preflight')
    client = PaidClient(BUDGET_DB,getattr(args,'series','collection'))
    sys.path.insert(0,str(TAU/'src'))
    os.environ['TAU2_DATA_DIR']=str(TAU/'data')
    os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
    from loguru import logger
    logger.remove();logger.add(sys.stderr,level='WARNING')
    from tau2.agent.llm_agent import LLMAgent
    from tau2.user.user_simulator import UserSimulator
    from tau2.data_model.tasks import Task
    from tau2.domains.banking_knowledge.environment import get_environment
    from tau2.orchestrator.orchestrator import Orchestrator
    from tau2.runner.simulation import run_simulation
    from tau2.evaluator.evaluator import EvaluationType
    raw_folder = args.root/'trajectories';raw_folder.mkdir(exist_ok=True)
    for task_id in selected[:args.episodes]:
        episode_id=(plan['namespace']+'/' if plan.get('namespace') else '')+task_id
        target = raw_folder/(task_id+'.json')
        if target.exists():
            print(dumps({'task':task_id,'status':'already_recorded'}),flush=True);continue
        # A crash leaves paid calls but no episode. Do not silently rerun native execution.
        with connect(client.path) as db:
            exists=db.execute('SELECT 1 FROM api_calls WHERE series=? AND call_id LIKE ?',(client.series,episode_id+'/%')).fetchone()
        if exists:
            raise BudgetError('partial episode found: inspect paid journal before restarting native execution')
        task = Task.model_validate_json((TAU/'data/tau2/domains/banking_knowledge/tasks'/f'{task_id}.json').read_text())
        env = get_environment(retrieval_variant='bm25')
        agent = LLMAgent(tools=env.get_tools(),domain_policy=env.get_policy(),llm=DEEPSEEK,
                         llm_args={'pilot_role':'agent','num_retries':0})
        user = UserSimulator(tools=env.get_user_tools(include=task.user_tools) or None,
                             instructions=str(task.user_scenario),llm=DEEPSEEK,
                             llm_args={'pilot_role':'simulator','num_retries':0})
        orchestrator = Orchestrator(domain='banking_knowledge',agent=agent,user=user,
            environment=env,task=task,max_steps=80,max_errors=5,seed=25,timeout=900,
            simulation_id='system-one-api-v1-'+task_id)
        record = {'task_id':task_id,'episode_id':episode_id,'started_at':utc(),'versions':code_manifest()}
        stop_budget=False
        try:
            with native_transport(client,episode_id):
                result = run_simulation(orchestrator,evaluation_type=EvaluationType.ENV,
                                        env_kwargs={'retrieval_variant':'bm25'})
            record.update(status='completed',native=result.model_dump(mode='json'))
        except Exception as exc:
            stop_budget=isinstance(exc,BudgetError)
            record.update(status='failed',error={'type':type(exc).__name__},
                          native={'messages':[m.model_dump(mode='json') for m in orchestrator.get_messages()]})
            # Secret-safe detailed diagnostic for known local exceptions only.
            if isinstance(exc,(ValueError,AssertionError,ImportError,AttributeError,BudgetError)):
                record['error']['detail']=str(exc)[:1000]
        record.update(finished_at=utc(),budget=client.summary())
        write_json(target,record)
        print(dumps({'task':task_id,'status':record['status'],'messages':len(record['native']['messages']),'budget':client.summary()}),flush=True)
        if stop_budget or client.summary()['unresolved'] or client.summary()['charged_or_held_usd']>=client.summary()['limit_usd']:
            break


def tokenizer_profile():
    verify_checkpoint()
    sys.path.insert(0,str(LAYA))
    from laya.agent import _fix_tokenizer_config
    from transformers import AutoTokenizer
    from laya.train import to_internal
    from laya.common import state_room
    _fix_tokenizer_config(str(CHECKPOINT))
    tok=AutoTokenizer.from_pretrained(str(CHECKPOINT/'tokenizer'),local_files_only=True)
    q=to_internal('useful',QUESTION)
    rooms={n:state_room(tok,q,n,256) for n in [1024,4096,8192]}
    return tok,rooms


def verify_checkpoint():
    manifest=json.loads((ROOT/'experiments/system-one-pilot/checkpoint-manifest.json').read_text())
    checkpoint=next(c for c in manifest['checkpoints'] if c['kind']=='multilingual')
    for entry in checkpoint['files']:
        verify_file(CHECKPOINT/entry['file'],entry['sha256'])


def extract(args):
    allowed=set(getattr(args,'allowed_splits',['train']))
    if not allowed or not allowed <= {'train','dev'}:raise ValueError('test extraction forbidden')
    if (args.root/'queue.jsonl').exists():
        raise ValueError('extraction already exists; use a new versioned output root for changes')
    tok,rooms=tokenizer_profile()
    count=lambda text:len(tok.encode(text,add_special_tokens=False))
    split=json.loads(SPLIT.read_text())
    rows,snaps,coverage,errors,episode_records=[],[],[],[],[]
    for path in sorted((args.root/'trajectories').glob('*.json')):
        episode=json.loads(path.read_text());task_id=episode['task_id']
        if split['tasks'][task_id]['split'] not in allowed: raise ValueError('split not allowed for extraction')
        messages=episode['native']['messages']
        cutoffs=[]
        last_pool_search=None
        for cutoff in range(1,len(messages)+1):
            try: snap=observed_state(messages,cutoff)
            except ValueError as exc:
                # Pending batches are normal between tool messages; parse failures are not.
                if 'incomplete tool batch' not in str(exc):
                    errors.append({'task_id':task_id,'cutoff':cutoff,
                        'code':'KB_PARSE_ERROR' if 'formatter' in str(exc) else 'SNAPSHOT_ERROR','reason':str(exc)})
                continue
            search=json.loads(snap['state'])['search_context']
            signature=digest(search)
            if snap['pool'] and signature!=last_pool_search:
                cutoffs.append(snap);last_pool_search=signature
        positions=sorted({round(i*(len(cutoffs)-1)/max(1,min(3,len(cutoffs))-1)) for i in range(min(3,len(cutoffs)))})
        episode_records.append({'episode_id':episode['episode_id'],'task_id':task_id,
            'source_sha256':filehash(path),'collection_status':episode['status'],
            'messages':len(messages),'retrieval_states_seen':len(cutoffs),
            'chosen_cutoffs':[cutoffs[i]['cutoff'] for i in positions],
            'exclusion':'no_observed_KB' if not cutoffs else None})
        for pos in positions:
            snap=cutoffs[pos]
            snap_id=digest([task_id,snap['snapshot_sha256']])
            snap.update(id=snap_id,task_id=task_id,episode_id=episode['episode_id'])
            snaps.append(snap)
            state_input={'input':{'state':snap['state'],'candidate':''}}
            state_tokens=count(input_text(state_input))
            for doc in snap['pool']:
                format_candidate=lambda body:'Title: '+doc['title']+'\nEvidence:\n'+body
                full={'input':{'state':snap['state'],'candidate':format_candidate(doc['content'])}}
                lengths={str(n):{'tokens':count(input_text(full)),'full_sequence_tokens':count(input_text(full))+n-room,'room':room,
                    'status':'STATE_OVERFLOW' if state_tokens>room else ('accepted' if count(input_text(full))<=room else 'CANDIDATE_OVERFLOW')}
                    for n,room in rooms.items()}
                parts=None if state_tokens>rooms[4096] else structural_parts(doc['content'],
                    lambda body:count(input_text({'input':{'state':snap['state'],'candidate':format_candidate(body)}}))<=rooms[4096])
                status='STATE_OVERFLOW' if state_tokens>rooms[4096] else ('accepted' if parts else 'CANDIDATE_OVERFLOW')
                coverage.append({'snapshot_id':snap_id,'episode_id':episode['episode_id'],'document_id':doc['document_id'],
                                 'lengths':lengths,'structural_4096':status,'parts':len(parts or [])})
                for part in parts or [{'text':doc['content'],'spans':[[0,len(doc['content'])]]}]:
                    inp={'state':snap['state'],'candidate':format_candidate(part['text'])}
                    row={'id':digest([REPRESENTATION,snap_id,doc['candidate_id'],part['spans']])[:24],
                         'task_id':task_id,**split['tasks'][task_id],'episode_id':episode['episode_id'],
                         'snapshot_id':snap_id,'cutoff':snap['cutoff'],'representation':REPRESENTATION,
                         'document_id':doc['document_id'],'title':doc['title'],'content_sha256':doc['content_sha256'],
                         'source_spans':part['spans'],'provenance':doc['provenance'],
                         'input':inp,'input_sha256':digest(inp),'admission':status,
                         'tokens':count(input_text({'input':inp})),'label':None}
                    rows.append(row)
    validate_rows(rows,split)
    if getattr(args,'per_family',None):
        from .adaptation import select_family_cards
        selected=select_family_cards(rows,args.target,args.per_family)
    else:selected=select_cards(rows,target=getattr(args,'target',30))
    from laya.train import to_internal,make_item,encode_item
    question=to_internal('useful',QUESTION)
    for row in selected:
        state_ids=tok.encode(input_text(row),add_special_tokens=False)
        if len(state_ids)>rooms[4096]:raise ValueError('selected input overflow')
        item,error=make_item(tok,question,[.5,.5],state_ids,256,4096)
        if error:raise ValueError(error)
        encoded=encode_item(tok,item,4096,256)
        row['scorer_input_ids']=list(encoded['ids'])
        assert len(row['scorer_input_ids'])==len(state_ids)+4096-rooms[4096],'serializer truncated input'
        row['full_sequence_tokens']=len(row['scorer_input_ids'])
        row['scorer_serialized']=tok.decode(row['scorer_input_ids'],skip_special_tokens=False)
        row['scorer_payload_sha256']=digest({'input_ids':row['scorer_input_ids'],'question':QUESTION,
                                          'profile':4096,'head_max_len':256})
    save_jsonl(args.root/'snapshots.jsonl',snaps)
    save_jsonl(args.root/'pool.jsonl',rows)
    save_jsonl(args.root/'queue.jsonl',selected)
    write_json(args.root/'admission.json',{'at':utc(),'profile':4096,'rooms':rooms,'head_max_len':256,
        'checkpoint_sha256':filehash(CHECKPOINT/'model.safetensors'),'tokenizer_sha256':filehash(CHECKPOINT/'tokenizer/tokenizer.json'),
        'pool_document_snapshots':len(coverage),'pool_rows':len(rows),'selected':len(selected),
        'counts':dict(collections.Counter(c['structural_4096'] for c in coverage)),
        'rows':coverage,'episodes':episode_records,
        'denominator':'all document versions in preselected retrieval snapshots, before admission or annotation; not all agent turns',
        'errors':errors,'versions':code_manifest()})
    print(dumps({'snapshots':len(snaps),'pool':len(rows),'selected':len(selected),'errors':len(errors)}))


def annotation_payload(row,model,rubric_text,version):
    response_format={'type':'json_object'} if version==1 else {
        'type':'json_schema','json_schema':{'name':'banking_usefulness_v1','strict':True,'schema':ANNOTATION_SCHEMA}}
    return {'model':model,'messages':[{'role':'system','content':rubric_text},
        {'role':'user','content':dumps(row['input'])}],'temperature':0,'reasoning':{'effort':'low'},
        'max_tokens':2048,'response_format':response_format}


def annotate(args):
    preflight(args.root/'preflight')
    rows=read_jsonl(args.root/'queue.jsonl')
    if not rows:raise ValueError('no admitted real cards; annotation stopped')
    validate_rows(rows,json.loads(SPLIT.read_text()))
    if any(digest(r['input'])!=r['input_sha256'] for r in rows):raise ValueError('queue input changed')
    client=PaidClient(BUDGET_DB,getattr(args,'series','annotation'))
    rubric_bytes=RUBRIC.read_bytes();rubric_text=rubric_bytes.decode('utf-8')
    rubric_hash=hashlib.sha256(rubric_bytes).hexdigest()
    plan={'annotation_version':args.version,'queue_sha256':filehash(args.root/'queue.jsonl'),
          'row_ids':[r['id'] for r in rows],'rubric_sha256':rubric_hash,
          'providers':{m:PROFILES[m]['endpoint'] for m in [DEEPSEEK,QWEN]},
          'response_format':annotation_payload(rows[0],DEEPSEEK,rubric_text,args.version)['response_format'],
          'temperature':0,'reasoning':{'effort':'low'},'max_tokens':2048,
          'previous_answers_visible_to_models':False}
    plan_path=args.root/f'annotation-plan-v{args.version}.json'
    if client.series!='annotation':
        plan.update(series=client.series,namespace=getattr(args,'namespace',''))
    if plan_path.exists():
        if json.loads(plan_path.read_text())!=plan:raise ValueError('annotation plan changed')
    else:write_json(plan_path,plan)
    folder=args.root/('annotations' if args.version==1 else 'annotations-v2');folder.mkdir(exist_ok=True)
    for row in rows:
        for model in [DEEPSEEK,QWEN]:
            tag='deepseek' if model==DEEPSEEK else 'qwen'
            target=folder/(row['id']+'-'+tag+'.json')
            if target.exists(): continue
            payload=annotation_payload(row,model,rubric_text,args.version)
            call_id=getattr(args,'namespace','')+('rubric-v1/' if args.version==1 else 'rubric-v1/schema-v2/')+row['id']+'/'+tag
            raw=client.complete(call_id,payload)
            record={'row_id':row['id'],'input_sha256':row['input_sha256'],'model':model,
                    'rubric_sha256':rubric_hash,'rubric_text':rubric_text,'annotation_version':args.version,
                    'parameters':{k:v for k,v in payload.items() if k!='messages'},
                    'call_id':call_id,'raw':raw,'at':utc()}
            try:
                choice=raw['choices'][0]
                record.update(status='valid',annotation=validate_annotation(choice['message']['content'],choice['finish_reason'],row['input']))
            except (ValueError,TypeError,KeyError,IndexError) as exc:
                record.update(status='technical_error',error_type=type(exc).__name__,error=str(exc)[:500])
            write_json(target,record)
            print(dumps({'row':row['id'],'model':tag,'status':record['status'],'budget':client.summary()}),flush=True)
    print(dumps(client.summary()))


def runtime_check(args):
    verify_checkpoint()
    from .model import runtime, admit
    torch,model,tok,cfg=runtime(LAYA,CHECKPOINT)
    from laya.train import to_internal, make_item, encode_item, _forward
    from laya.common import collate_items, state_room
    device=torch.device(args.device)
    if args.device=='mps' and not torch.backends.mps.is_available():raise RuntimeError('MPS unavailable')
    model.to(device).eval();q=to_internal('useful',QUESTION)
    records=[];rows=read_jsonl(args.root/'queue.jsonl')
    if not rows: raise ValueError('no admitted real train rows for runtime')
    # Three real rows spanning observed input lengths; no artificial padding.
    ordered=sorted(rows,key=lambda r:r['tokens'])
    indices=sorted({0,len(ordered)//2,len(ordered)-1})
    torch.set_num_threads(4)
    for i in indices:
        row=ordered[i];start=time.perf_counter()
        ids=admit(tok,input_text(row),state_room(tok,q,4096,256))
        item,error=make_item(tok,q,[.5,.5],ids,256,4096)
        if error: raise ValueError(error)
        encoded=encode_item(tok,item,4096,256)
        batch=collate_items([[encoded]],tok.pad_token_id)
        if row.get('scorer_input_ids') is not None:
            assert batch['input_ids'][0].tolist()==row['scorer_input_ids'],'stored serializer differs from runtime'
        with torch.inference_mode(): result=_forward(model,batch,device,False,True)
        if device.type=='mps':torch.mps.synchronize()
        elapsed=time.perf_counter()-start
        temperature=float(cfg.get('temperature_by_options',{}).get('noul:2',cfg['temperature'][2]))
        score=float(torch.softmax(result[0]/temperature,-1)[1].cpu())
        # This probes the 4096 profile; actual sequence lengths are recorded, not claimed as 4096.
        records.append({'row_id':row['id'],'input_sha256':row['input_sha256'],'input_tokens':len(ids),
            'full_sequence_tokens':int(batch['input_ids'].shape[-1]),'elapsed_seconds':elapsed,
            'logits':result.cpu().tolist(),'useful_score_published_calibration':score,'temperature':temperature,
            'output_finite':bool(torch.isfinite(result).all()),
            'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'mps_driver_bytes':torch.mps.driver_allocated_memory() if device.type=='mps' else None})
    write_json(args.root/('runtime-4096-'+args.device+'.json'),{'at':utc(),'device':str(device),'profile':4096,
        'frozen_adapted_same_profile':True,'training_run':False,'quality':'not measured; no human labels',
        'versions':code_manifest(),'records':records})
    print(dumps(records))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=DEFAULT_RUN)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('collect');p.add_argument('--episodes',type=int,choices=range(1,101));p.add_argument('--plan',type=Path);p.set_defaults(func=collect)
    p=sub.add_parser('extract');p.add_argument('--allowed-splits',nargs='+',choices=['train','dev'],default=['train']);p.add_argument('--target',type=int,default=30);p.add_argument('--per-family',type=int);p.set_defaults(func=extract)
    p=sub.add_parser('annotate');p.add_argument('--version',type=int,choices=[1,2],default=2);p.set_defaults(func=annotate)
    sub.add_parser('budget').set_defaults(func=lambda args:print(dumps({
        series:PaidClient(BUDGET_DB,series).summary() for series in ['collection','annotation']})))
    p=sub.add_parser('runtime');p.add_argument('--device',choices=['cpu','mps'],default='mps');p.set_defaults(func=runtime_check)
    args=parser.parse_args();args.root=args.root.resolve();args.func(args)


if __name__=='__main__':main()
