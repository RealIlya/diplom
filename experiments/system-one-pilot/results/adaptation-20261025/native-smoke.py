"""One old TRAIN card: verify native MLX feature -> CPU head gradient, not quality."""
import copy,json,os,time
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from scripts.system_one_pilot.compare import Kev,ROOT,PROTOCOL,load_cohort
from scripts.system_one_pilot.adapt_head import predict,train_one,probability
from scripts.system_one_pilot.data import write_json
import torch
p=json.loads(PROTOCOL.read_text());row=load_cohort(ROOT/p['cohort_source'],p)[0]
assert row['split']=='train';row=dict(row,role='train',defect=False)
start=time.perf_counter();adapter=Kev('kev-0.8b');adapter.sync();captured=[]
from kev.model import PointerHead
hook=adapter.model.head.register_forward_pre_hook(lambda module,inputs:captured.append(tuple(x.detach().clone() for x in inputs)))
enc,_=adapter.encode(row);native_p,_=adapter.forward(enc);adapter.sync();hook.remove()
assert len(captured)==1
initial=copy.deepcopy(adapter.model.head.state_dict());features={row['id']:captured[0]}
results={}
for loss in ['ce','brier']:
    head=PointerHead(captured[0][0].shape[0],dp=adapter.model.head.q.weight.shape[0]);head.load_state_dict(initial)
    z,_=predict(head,[row],features)
    delta=abs(probability(z[row['id']],adapter.temperature)-native_p);assert delta<1e-6
    config={'epochs':3,'batch_size':1,'seed':25,'lr':1e-4,'weight_decay':.01}
    curves=train_one(head,[row],features,loss,config)
    change=sum(float((head.state_dict()[k]-initial[k]).abs().sum()) for k in initial)
    assert change>0 and all(torch.isfinite(v).all() for v in head.state_dict().values())
    results[loss]={'epochs':3,'train_rows':1,'native_probability_delta':delta,'parameter_l1_change':change,'curves':curves}
write_json(ROOT/'experiments/system-one-pilot/results/adaptation-20261025/native-smoke.json',
           {'status':'passed','purpose':'engineering gradient smoke only; no quality/generalization claim',
            'source_row_id':row['id'],'split':'train','elapsed_seconds':time.perf_counter()-start,'results':results})
print('NATIVE_CPU_HEAD_GRADIENT_SMOKE_PASSED',json.dumps(results))
