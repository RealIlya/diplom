"""Narrow first-packet human exception: preserve full bounds, never retry a 504."""
import hashlib
import json
from .compare import filehash
from .data import digest,write_json
from .live_api import ROOT,PROFILES,connect,utc,dumps


def reconcile_provider_504s(ledger,approval_file):
    approval=json.loads(approval_file.read_text())
    protocol=ROOT/approval['protocol_path']
    if filehash(protocol)!=approval['protocol_sha256']:raise ValueError('approved protocol changed')
    p=json.loads(protocol.read_text())
    if (not approval.get('user_authorization') or approval.get('allowed_code')!=504
        or approval.get('requires_saved_generation_id') is not True
        or approval.get('keep_full_reserved_amount') is not True
        or approval.get('retry_failed_request') is not False
        or approval.get('other_unknowns_stop') is not True
        or approval.get('daily_limit_usd')!=1 or p.get('daily_limit_nusd')!=1_000_000_000
        or approval['namespace']!=p['namespace']+'/'
        or set(approval['series'])!=set(p['series_caps_nusd'])):
        raise ValueError('unsupported 504 approval scope')
    root=ROOT/p['root'];count=0
    with connect(ledger) as db:
        db.execute('BEGIN IMMEDIATE')
        rows=db.execute("SELECT c.* FROM api_calls c LEFT JOIN api_reconciliations r ON c.series=r.series AND c.call_id=r.call_id WHERE c.status IN ('unknown','unreconciled') AND r.call_id IS NULL").fetchall()
        for row in rows:
            if row['series'] not in approval['series'] or not row['call_id'].startswith(approval['namespace']) or row['actual_nusd'] is not None or not row['finished_at'] or not row['response']:continue
            stored=json.loads(row['response']);body=stored
            if 'http_status' in stored:
                if stored['http_status']!=504:continue
                try:body=json.loads(stored['body'])
                except (KeyError,TypeError,json.JSONDecodeError):continue
            request=json.loads(row['request']);profile=PROFILES.get(request.get('model'))
            error=body.get('error') or {};gid=body.get('id')
            if (error.get('code')!=504 or not isinstance(gid,str) or not gid
                or body.get('choices') or body.get('usage') or not profile
                or request.get('provider',{}).get('only')!=[profile['endpoint']]):continue
            header=db.execute("SELECT body FROM api_receipts WHERE series=? AND call_id=? AND kind='response_headers'",(row['series'],row['call_id'])).fetchone()
            if header and json.loads(header['body']).get('generation_id')!=gid:continue
            # Annotation failure needs a local technical record so a resumed annotator skips it.
            if '/rubric-v1/schema-v2/' in row['call_id']:
                suffix=row['call_id'].split('/rubric-v1/schema-v2/',1)[1]
                rid,tag=suffix.rsplit('/',1)
                queue=[json.loads(s) for s in (root/'queue.jsonl').read_text().splitlines() if s.strip()]
                cards={r['id']:r for r in queue}
                if rid not in cards or json.loads(request['messages'][1]['content'])!=cards[rid]['input']:
                    raise ValueError('504 annotation does not match frozen queue')
                expected_tag='deepseek' if request['model'].startswith('deepseek/') else 'qwen'
                if tag!=expected_tag:raise ValueError('504 annotator tag differs')
                rubric=request['messages'][0]['content']
                record={'row_id':rid,'input_sha256':cards[rid]['input_sha256'],'model':request['model'],
                        'rubric_sha256':hashlib.sha256(rubric.encode()).hexdigest(),'rubric_text':rubric,
                        'annotation_version':2,'parameters':{k:v for k,v in request.items() if k!='messages'},
                        'call_id':row['call_id'],'raw':stored,'at':row['finished_at'],'status':'technical_error',
                        'error_type':'Provider504FullBoundAccounted','error':'Provider504 with savedID, fullreserved amount retained, no retry'}
                folder=root/'annotations-v2';folder.mkdir(exist_ok=True);target=folder/(rid+'-'+tag+'.json')
                if target.exists():
                    old=json.loads(target.read_text())
                    if old['call_id']!=row['call_id'] or digest(old['raw'])!=digest(stored):raise ValueError('504 technical receipt differs')
                else:write_json(target,record)
            evidence={'approval_sha256':filehash(approval_file),'protocol_sha256':approval['protocol_sha256'],
                      'response_sha256':digest(stored),'generation_id':gid,'request_hash':row['request_hash'],
                      'reserved_nusd_retained':row['reserved_nusd'],'actual_cost_remains_unknown':True,
                      'reason':approval['user_authorization']}
            db.execute('INSERT INTO api_reconciliations VALUES(?,?,?,?,?)',
                       (row['series'],row['call_id'],'human_authorized_provider504_full_bound',dumps(evidence),utc()))
            count+=1
    return count
