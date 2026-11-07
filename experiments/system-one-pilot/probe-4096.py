"""Synthetic tensor capacity check only; never a dataset card or quality measurement."""
import json
from pathlib import Path
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.system_one_pilot.live import LAYA,CHECKPOINT,verify_checkpoint,read_jsonl,code_manifest
from scripts.system_one_pilot.model import runtime,QUESTION,input_text,admit
from scripts.system_one_pilot.data import write_json

verify_checkpoint()
torch,model,tok,cfg=runtime(LAYA,CHECKPOINT)
from laya.train import to_internal,make_item,encode_item,_forward
from laya.common import state_room,collate_items
q=to_internal('useful',QUESTION)
room=state_room(tok,q,4096,256)
folder=ROOT/'artifacts/system-one-pilot/archival-runtime-validation-v1'
rows=read_jsonl(folder/'queue.jsonl')
row=max(rows,key=lambda r:r['tokens'])
observed_ids=admit(tok,input_text(row),room)
ids=(observed_ids*((room+len(observed_ids)-1)//len(observed_ids)))[:room]
item,error=make_item(tok,q,[.5,.5],ids,256,4096)
assert error is None,error
batch=collate_items([[encode_item(tok,item,4096,256)]],tok.pad_token_id)
assert batch['input_ids'].shape[-1]==4096,batch['input_ids'].shape
assert torch.backends.mps.is_available(),'MPS unavailable'
model.to('mps').eval();torch.set_num_threads(4)
torch.mps.synchronize();start=time.perf_counter()
with torch.inference_mode():output=_forward(model,batch,torch.device('mps'),False,True)
torch.mps.synchronize()
record={'kind':'synthetic_capacity_only','dataset_card':False,'human_label':None,'quality':'not measured',
    'padding_method':'repeat observed token IDs to fill state room; no scientific input claim',
    'source_row':row['id'],'profile':4096,'actual_sequence_tokens':batch['input_ids'].shape[-1],
    'elapsed_seconds':time.perf_counter()-start,'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    'mps_driver_bytes':torch.mps.driver_allocated_memory(),'finite':torch.isfinite(output).all().item(),
    'versions':code_manifest()}
assert record['finite']
write_json(folder/'capacity-4096-mps.json',record)
print(json.dumps({k:v for k,v in record.items() if k!='versions'}))
