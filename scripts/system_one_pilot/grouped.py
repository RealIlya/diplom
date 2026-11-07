"""Independent Noul branches over one observed state; no labels enter the encoder."""
import math
from .model import QUESTION


def candidate_groups(pool,size=5):
    if type(size) is not int or size<1:raise ValueError('invalid group size')
    for i in range(0,len(pool),size):yield pool[i:i+size]


def group_payload(state,candidates):
    ids=[d['candidate_id'] for d in candidates]
    if not ids or len(set(ids))!=len(ids) or not all(isinstance(x,str) and x for x in ids):
        raise ValueError('invalid candidate IDs')
    return {'state':'Observed conversation:\n'+state,'questions':{
        d['candidate_id']:{'type':'noul','instructions':QUESTION['instructions']+
                          '\nCandidate evidence:\nTitle: '+d['title']+'\nEvidence:\n'+d['content']}
        for d in candidates}}


def binary_probabilities(logits):
    if not logits or any(len(z)!=2 or not all(math.isfinite(float(x)) for x in z) for z in logits):
        raise ValueError('invalid binary logits')
    result=[]
    for no,yes in logits:
        d=float(yes)-float(no)
        result.append(1/(1+math.exp(-d)) if d>=0 else math.exp(d)/(1+math.exp(d)))
    return result


class GroupedKev:
    representation='context-v0-noul-branches-v1'

    def __init__(self,adapter=None,group_size=5):
        if type(group_size) is not int or group_size<1:raise ValueError('invalid group size')
        if adapter is None:
            from .compare import Kev
            adapter=Kev('kev-0.8b')
        self.adapter=adapter;self.group_size=group_size

    def score_many(self,state,pool):
        if not pool:return []
        if len({d['candidate_id'] for d in pool})!=len(pool):raise ValueError('duplicate candidate IDs')
        from kev.api import SystemOneRequest,to_record
        result=[]
        for group in candidate_groups(pool,self.group_size):
            payload=group_payload(state,group)
            record,meta=to_record(SystemOneRequest(**payload))
            enc=self.adapter.model.encode(self.adapter.tok,record,strict=True,max_state=8192,max_branch=8192)
            if enc['state_truncated']:raise ValueError('group state truncated')
            logits=self.adapter.model.forward(enc)
            if len(logits)!=len(group) or [m['id'] for m in meta]!=[d['candidate_id'] for d in group]:
                raise ValueError('group output cardinality/identity differs')
            result.extend(binary_probabilities([z.tolist() for z in logits]))
        return result


class BatchKev:
    """Control: original binary rows, padded together without prefix sharing."""
    representation='context-v0-original-batch-v1'

    def __init__(self,adapter,group_size=5):
        if type(group_size) is not int or group_size<1:raise ValueError('invalid group size')
        self.adapter=adapter;self.group_size=group_size

    def score_many(self,state,pool):
        if len({d['candidate_id'] for d in pool})!=len(pool):raise ValueError('duplicate candidate IDs')
        result=[]
        for group in candidate_groups(pool,self.group_size):
            encs=[self.adapter.encode({'input':{'state':state,'candidate':'Title: '+d['title']+'\nEvidence:\n'+d['content']}})[0] for d in group]
            # Bound padded batch tokens, using the same frozen source budget as KEV.
            width=max(1,16384//max(len(e['ids']) for e in encs))
            for part in candidate_groups(encs,width):
                h=self.adapter.model._hidden([e['ids'] for e in part])
                logits=[self.adapter.model._logits(h[i],e['decide_idx'][0],e['opt_idx'][0]).tolist() for i,e in enumerate(part)]
                result.extend(binary_probabilities(logits))
        return result
