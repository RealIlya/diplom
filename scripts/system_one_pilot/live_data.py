"""Versioned observation-only context, conservative structural views and rubric checks."""
import collections
import copy
import json
import re

from .data import digest, KB_TOOLS, parse_kb

REPRESENTATION = 'context-v0-structural-v2'
LABELS = {'useful', 'irrelevant', 'uncertain'}
ANNOTATION_SCHEMA={
    'type':'object','additionalProperties':False,
    'required':['label','reason','conditions','defect','quotes'],
    'properties':{
        'label':{'type':'string','enum':['useful','irrelevant','uncertain']},
        'reason':{'type':'string'},'conditions':{'type':'string'},'defect':{'type':'boolean'},
        'quotes':{'type':'array','minItems':1,'maxItems':4,'items':{
            'type':'object','additionalProperties':False,'required':['source','text'],
            'properties':{'source':{'type':'string','enum':['state','candidate']},'text':{'type':'string'}}}}}}


def observed_state(messages, cutoff):
    if not 0<=cutoff<=len(messages):raise ValueError('invalid cutoff')
    snap={'cutoff':cutoff,'history':[],'pool':[],'kb_history_indices':[]}
    dialogue, events, calls, included, visible = [], [], {}, set(), []
    pool,pending={},set()
    prior_assistant = None
    search = None
    provenance = collections.defaultdict(list)
    for i, raw in enumerate(messages[:cutoff]):
        role = raw.get('role')
        if role not in {'user','assistant','tool'} or (role=='user' and raw.get('tool_calls')) or (role=='tool' and raw.get('requestor')!='assistant'):
            continue
        visible.append(i)
        if role == 'assistant':
            if pending:raise ValueError('incomplete tool batch before assistant')
            if raw.get('content'):
                prior_assistant = {'event':i, 'role':role, 'content':raw['content']}
            for call in raw.get('tool_calls') or []:
                calls[call['id']] = {k:copy.deepcopy(call[k]) for k in ['id','name','arguments'] if k in call}
                calls[call['id']]['event'] = i
                pending.add(call['id'])
        elif role == 'user':
            if prior_assistant and prior_assistant['event'] not in included:
                dialogue.append(prior_assistant)
                included.add(prior_assistant['event'])
            dialogue.append({'event':i,'role':'user','content':raw.get('content') or ''})
            included.add(i)
        elif role == 'tool':
            call = calls.get(raw.get('id'))
            if not call:
                raise ValueError('unmatched observed tool result')
            if raw['id'] not in pending:raise ValueError('duplicate observed tool result')
            pending.remove(raw['id'])
            record = dict(call, result_event=i, content=raw.get('content') or '',error=bool(raw.get('error',False)))
            included.update([i, call['event']])
            if call['name'] in KB_TOOLS:
                docs = [] if record['error'] else parse_kb(record['content'])
                search = {k:v for k,v in record.items() if k != 'content'}
                search['outcome'] = 'error' if record['error'] else ('documents_received' if docs else 'no_documents')
                if record['error']:search['error_content']=record['content']
                for doc in docs:
                    key=doc['document_id']+'@'+doc['content_sha256']
                    provenance[key].append({'event':i,'tool_call_id':raw['id']})
                    if key not in pool:pool[key]=dict(doc,candidate_id=key,source_event=i,tool_call_id=raw['id'])
                snap['kb_history_indices'].append(len(snap['history']))
            else:
                events.append(record)
        snap['history'].append({k:copy.deepcopy(raw[k]) for k in ['role','content','tool_calls','id','requestor','name','error'] if k in raw})
    if pending:raise ValueError('incomplete tool batch at cutoff')
    state = {'dialogue':dialogue, 'search_context':search, 'tool_events':events}
    snap['pool']=list(pool.values())
    for doc in snap['pool']:
        doc['provenance'] = provenance[doc['candidate_id']]
    snap['state'] = json.dumps(state, ensure_ascii=False, separators=(',',':'))
    snap['representation'] = REPRESENTATION
    snap['included_events'] = sorted(included)
    snap['excluded_observed_events'] = sorted(set(visible)-included)
    snap['snapshot_sha256'] = digest({k:v for k,v in snap.items() if k!='snapshot_sha256'})
    return snap


def structural_parts(text, fits):
    if fits(text):
        return [{'text':text, 'spans':[[0,len(text)]]}]
    # Keep every paragraph with an explicit applicability/exception cue in every view.
    # This intentionally sacrifices coverage when cross-section conditions are long.
    blocks = []
    for match in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', text):
        a,b = match.span()
        while b > a and text[b-1].isspace(): b -= 1
        blocks.append([a,b])
    if len(blocks)<2:
        return None
    guards = set([0])
    for i,(a,b) in enumerate(blocks):
        if re.search(r'(?im)^\s*#{1,6}\s|\b(if|unless|except|only|must|condition\w*|eligib\w*|exclu\w*|require\w*|assum\w*|subject|provided|depend\w*|otherwise|without|before|after|when|where|not\s+available)\b',text[a:b]):
            guards.add(i)
    result = []
    for i in range(len(blocks)):
        indices = sorted(guards | {i})
        spans = [blocks[k] for k in indices]
        body = '\n\n'.join(text[a:b] for a,b in spans)
        if not fits(body):
            return None
        if not any(p['spans']==spans for p in result):
            result.append({'text':body,'spans':spans})
    return result


def select_cards(rows, target=30, seed=25):
    groups = collections.defaultdict(lambda:collections.defaultdict(list))
    for row in rows:
        if row['admission']=='accepted':
            groups[row['episode_id']][row['snapshot_id']].append(row)
    episode_queues = {}
    for episode, snapshots in groups.items():
        buckets = [sorted(values,key=lambda r:digest([seed,r['id']])) for _,values in sorted(snapshots.items())]
        ordered = []
        while any(buckets):
            for bucket in buckets:
                if bucket: ordered.append(bucket.pop(0))
        episode_queues[episode] = ordered[:10]
    selected = []
    while len(selected)<target and any(episode_queues.values()):
        for episode in sorted(episode_queues,key=lambda x:digest([seed,x])):
            if episode_queues[episode] and len(selected)<target:
                selected.append(episode_queues[episode].pop(0))
    return selected


def validate_annotation(text, finish, inputs):
    if finish != 'stop':
        raise ValueError('incomplete response: '+str(finish))
    value = json.loads(text)
    if not isinstance(value,dict) or set(value) != {'label','reason','conditions','defect','quotes'}:
        raise ValueError('annotation schema keys')
    if value['label'] not in LABELS or type(value['defect']) is not bool:
        raise ValueError('annotation schema types')
    if not isinstance(value['reason'],str) or not value['reason'].strip() or not isinstance(value['conditions'],str):
        raise ValueError('annotation reason/conditions')
    if not isinstance(value['quotes'],list) or not 1 <= len(value['quotes']) <= 4:
        raise ValueError('annotation quotes required')
    for quote in value['quotes']:
        if not isinstance(quote,dict) or set(quote)!={'source','text'} or quote['source'] not in inputs:
            raise ValueError('annotation quote schema')
        if not isinstance(quote['text'],str) or not quote['text'].strip() or quote['text'] not in inputs[quote['source']]:
            raise ValueError('annotation quote absent from input')
        a = inputs[quote['source']].index(quote['text'])
        quote['span'] = [a,a+len(quote['text'])]
    return value
