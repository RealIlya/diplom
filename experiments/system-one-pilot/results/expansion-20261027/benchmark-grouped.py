"""Local engineering comparison: serialization drift is separate from grouping drift."""
import collections,json,os,time
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',TOKENIZERS_PARALLELISM='false')
from scripts.system_one_pilot.compare import Kev,memory,filehash
from scripts.system_one_pilot.grouped import GroupedKev,BatchKev
from scripts.system_one_pilot.data import digest
root=Path.cwd();out=root/'artifacts/system-one-pilot/expansion-v1/grouped-benchmark-v2';out.mkdir(exist_ok=False)
source=root/'artifacts/system-one-pilot/adaptation-v1/pool.jsonl'
groups=collections.defaultdict(list)
for line in source.read_text().splitlines():
 r=json.loads(line)
 if r['split']=='train' and r['admission']=='accepted':groups[r['snapshot_id']].append(r)
chosen=[]
for sid,rows in sorted(groups.items(),key=lambda p:digest([25,p[0]])):
 docs={}
 for r in sorted(rows,key=lambda r:r['id']):docs.setdefault(r['document_id'],r)
 if len(docs)>=5:chosen.append(list(docs.values())[:5])
 if len(chosen)==3:break
assert len(chosen)==3
adapter=Kev('kev-0.8b');adapter.sync();records=[]
for mode in ['scalar','original_batch5','branches1','branches5']:
 scorer=BatchKev(adapter) if mode=='original_batch5' else GroupedKev(adapter,1 if mode=='branches1' else 5)
 for phase in ['warmup','measure0','measure1']:
  for rows in chosen:
   state=rows[0]['input']['state'];assert all(r['input']['state']==state for r in rows)
   pool=[{'candidate_id':r['id'],'title':r['title'],'content':r['input']['candidate'].split('\nEvidence:\n',1)[1]} for r in rows]
   adapter.sync();adapter.mx.reset_peak_memory();start=time.perf_counter()
   values=([adapter.forward(adapter.encode(r)[0])[0] for r in rows] if mode=='scalar' else scorer.score_many(state,pool))
   adapter.sync();elapsed=time.perf_counter()-start
   rec={'mode':mode,'phase':phase,'snapshot_id':rows[0]['snapshot_id'],'ids':[r['id'] for r in rows],
        'state_sha256':digest(state),'probabilities':values,'seconds':elapsed,'memory':memory('mlx')}
   records.append(rec);print(json.dumps({k:rec[k] for k in ['mode','phase','seconds']}),flush=True)
(out/'records.json').write_text(json.dumps(records,indent=2))
measured=[r for r in records if r['phase'].startswith('measure')]
by={(r['mode'],r['phase'],r['snapshot_id']):r for r in measured}
def delta(a,b):
 return max(abs(x-y) for (mode,phase,sid),r in by.items() if mode==a
            for x,y in zip(r['probabilities'],by[(b,phase,sid)]['probabilities']))
summary={'model':'kev-0.8b','groups':3,'candidates_per_group':5,'repeats':2,'training':False,'api_calls':0,
 'source_sha256':filehash(source),'records_sha256':filehash(out/'records.json'),
 'modes':{mode:{'measured_groups':len(rs:=[r for r in measured if r['mode']==mode]),
                'total_seconds':sum(r['seconds'] for r in rs),
                'max_mlx_peak_bytes':max(r['memory']['mlx_peak_bytes'] for r in rs)} for mode in ['scalar','original_batch5','branches1','branches5']},
 'max_probability_delta':{'original_batch_vs_scalar':delta('original_batch5','scalar'),
  'grouping_same_new_serializer':delta('branches5','branches1'),
  'new_vs_old_serializer':delta('branches1','scalar')},
 'scope':'engineering timing on3saved train snapshots, fixed mode order; no heldout quality claim; raw logits not rounded'}
(out/'summary.json').write_text(json.dumps(summary,indent=2))
(root/'experiments/system-one-pilot/results/expansion-20261027/grouped-benchmark.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
