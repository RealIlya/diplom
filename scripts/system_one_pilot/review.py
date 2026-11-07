"""Single-Mac SQLite review, append-only audit, JSONL export and online backup."""
import argparse
import hashlib
from datetime import datetime, timezone
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import uuid
from urllib.parse import urlparse, parse_qs

from .data import digest, write_json
from .live_api import connect, dumps, utc
from .live_data import LABELS,validate_annotation
from .live import DEFAULT_RUN, read_jsonl, annotation_payload
from .live import BUDGET_DB, DEEPSEEK, QWEN
from .cli import filehash
from .model import input_text, QUESTION


def translation_sources(body,answers):
    sources={body['input']['state'],body['input']['candidate'],body['title']}
    for answer in answers or []:
        if answer.get('rubric_text'):sources.add(answer['rubric_text'])
        annotation=answer.get('annotation') or {}
        sources.update(annotation[k] for k in ['reason','conditions'] if annotation.get(k))
        sources.update(q['text'] for q in annotation.get('quotes',[]))
    return sources


class ReviewStore:
    def __init__(self,path):
        self.path=Path(path)
        with connect(self.path) as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY, input_hash TEXT NOT NULL, body TEXT NOT NULL,
                annotations TEXT NOT NULL, kind TEXT NOT NULL, required INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS reviews (
                card_id TEXT PRIMARY KEY REFERENCES cards(id), revision INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending', draft TEXT NOT NULL DEFAULT '{}',
                first_label TEXT, revealed INTEGER NOT NULL DEFAULT 0, confirmed TEXT,
                updated_at TEXT);
              CREATE TABLE IF NOT EXISTS review_events (
                id INTEGER PRIMARY KEY, card_id TEXT NOT NULL, input_hash TEXT NOT NULL,
                action TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL,
                at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS review_session (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS review_translation (
                id INTEGER PRIMARY KEY CHECK(id=1), bundle_hash TEXT NOT NULL, body TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS trusted_labels (card_id TEXT PRIMARY KEY REFERENCES cards(id), body TEXT NOT NULL);
              INSERT OR IGNORE INTO review_session VALUES(1,'{}');
              CREATE TRIGGER IF NOT EXISTS immutable_cards BEFORE UPDATE ON cards
                BEGIN SELECT RAISE(ABORT,'immutable card/input/LLM answers'); END;
              CREATE TRIGGER IF NOT EXISTS no_card_delete BEFORE DELETE ON cards
                BEGIN SELECT RAISE(ABORT,'immutable card'); END;
              CREATE TRIGGER IF NOT EXISTS immutable_review_events BEFORE UPDATE ON review_events
                BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
              CREATE TRIGGER IF NOT EXISTS no_review_event_delete BEFORE DELETE ON review_events
                BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
              CREATE TRIGGER IF NOT EXISTS immutable_translation BEFORE UPDATE ON review_translation
                BEGIN SELECT RAISE(ABORT,'immutable translation version'); END;
              CREATE TRIGGER IF NOT EXISTS no_translation_delete BEFORE DELETE ON review_translation
                BEGIN SELECT RAISE(ABORT,'immutable translation version'); END;
              CREATE TRIGGER IF NOT EXISTS immutable_trusted_labels BEFORE UPDATE ON trusted_labels
                BEGIN SELECT RAISE(ABORT,'immutable trusted label'); END;
              CREATE TRIGGER IF NOT EXISTS no_trusted_label_delete BEFORE DELETE ON trusted_labels
                BEGIN SELECT RAISE(ABORT,'immutable trusted label'); END;
            ''')

    def resolutions(self):
        with connect(self.path) as db:return {r['card_id']:json.loads(r['body']) for r in db.execute('SELECT * FROM trusted_labels')}

    def accept_models(self,adjudications):
        if not isinstance(adjudications,dict):raise ValueError('invalid agent adjudications')
        if self.session().get('hold')=='yes':raise ValueError('review paused; investigate before accepting labels')
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT c.*,r.status FROM cards c JOIN reviews r ON r.card_id=c.id').fetchall()
            if set(adjudications)-{r['id'] for r in rows}:raise ValueError('unknown agent adjudication card')
            for row in rows:
                if row['status']!='pending':continue  # Preserve existing human work.
                body=json.loads(row['body']);answers=json.loads(row['annotations'])
                if digest(body['input'])!=row['input_hash'] or len(answers)!=2 or {a['model'] for a in answers}!={DEEPSEEK,QWEN}:
                    raise ValueError('trusted model pair/input mismatch')
                override=adjudications.get(row['id'])
                if override is not None:
                    if override.get('input_sha256')!=row['input_hash'] or not isinstance(override.get('reason_ru'),str) or not override['reason_ru'].strip():
                        raise ValueError('agent adjudication input/reason mismatch')
                    annotation=validate_annotation(dumps(override['annotation']),'stop',body['input'])
                    source='agent_adjudication';reason=override['reason_ru']
                elif all(a['status']=='valid' and not a['annotation'].get('defect') for a in answers) and answers[0]['annotation']['label']==answers[1]['annotation']['label']:
                    annotation=answers[0]['annotation'];source='llm_consensus'
                    reason='DeepSeek и Qwen3.8 независимо согласны; метка принята по доверенной политике инициатора.'
                else:raise ValueError('agent adjudication required for '+row['id'])
                resolution={'schema':'trusted-label-v1','policy':'deepseek-qwen-agent-v1','row_id':row['id'],
                    'input_sha256':row['input_hash'],'human_review':False,'source':source,
                    'annotation':annotation,'reason_ru':reason,'llm_annotations_sha256':digest(answers),
                    'training_eligible':annotation['label']!='uncertain' and not annotation.get('defect'),
                    'at':utc()}
                old=db.execute('SELECT body FROM trusted_labels WHERE card_id=?',(row['id'],)).fetchone()
                if old:
                    original=json.loads(old['body']);resolution['at']=original['at']
                    if original!=resolution:raise ValueError('trusted label changed; new version required')
                else:db.execute('INSERT INTO trusted_labels VALUES(?,?)',(row['id'],dumps(resolution)))
        session=self.session()
        if session.get('filter')=='required':session['filter']='all'
        if session.get('status')=='pending':session['status']='all'
        self.set_session(session)

    def import_translations(self,bundle):
        if not isinstance(bundle,dict) or bundle.get('schema')!='review-ru-v1' or not isinstance(bundle.get('entries'),list):
            raise ValueError('invalid translation schema')
        entries=bundle['entries'];sources=[]
        for entry in entries:
            if not isinstance(entry,dict) or set(entry)!={'source','source_sha256','ru'} or not isinstance(entry['source'],str) or not isinstance(entry['ru'],str) or not entry['ru'].strip():
                raise ValueError('invalid translation entry')
            if hashlib.sha256(entry['source'].encode()).hexdigest()!=entry['source_sha256']:
                raise ValueError('translation source hash mismatch')
            sources.append(entry['source'])
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE');known=set()
            for row in db.execute('SELECT body,annotations FROM cards'):
                known.update(translation_sources(json.loads(row['body']),json.loads(row['annotations'])))
            if len(sources)!=len(set(sources)) or set(sources)!=known or not known:
                raise ValueError('translation coverage differs from original review sources')
            old=db.execute('SELECT bundle_hash FROM review_translation').fetchone()
            if old:
                if old['bundle_hash']!=digest(bundle):raise ValueError('immutable translation changed; preserve this review version')
                return
            # shortcut: fixed pilot translation; use a new review version when correcting it.
            db.execute('INSERT INTO review_translation VALUES(1,?,?)',(digest(bundle),dumps(bundle)))

    def translation_bundle(self):
        with connect(self.path) as db:row=db.execute('SELECT body FROM review_translation').fetchone()
        return json.loads(row['body']) if row else None

    def import_cards(self,rows,annotations,control_seed=25):
        kinds={}
        for row in rows:
            answers=annotations.get(row['id'],[])
            if any(a.get('input_sha256')!=row['input_sha256'] or a.get('row_id')!=row['id'] for a in answers):
                raise ValueError('annotation input/card version mismatch')
            if len({a.get('model') for a in answers})!=len(answers) or len({a.get('rubric_sha256') for a in answers})>1:
                raise ValueError('annotation models/rubric mismatch')
            if len(answers)!=2 or any(a.get('status')!='valid' for a in answers):kind='technical_error'
            elif any(a['annotation'].get('defect') for a in answers):kind='model_defect'
            elif any(a['annotation']['label']=='uncertain' for a in answers):kind='uncertain'
            elif answers[0]['annotation']['label']!=answers[1]['annotation']['label']:kind='conflict'
            else:kind='agreement'
            kinds[row['id']]=kind
        controls=set(sorted((rid for rid,k in kinds.items() if k=='agreement'),
                            key=lambda rid:digest([control_seed,rid]))[:7])
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            for row in rows:
                if digest(row['input'])!=row['input_sha256']:raise ValueError('input hash mismatch')
                kind='control' if row['id'] in controls else kinds[row['id']]
                values=(row['id'],row['input_sha256'],dumps(row),dumps(annotations.get(row['id'],[])),kind,int(kind!='agreement'))
                old=db.execute('SELECT * FROM cards WHERE id=?',(row['id'],)).fetchone()
                if old:
                    if tuple(old)!=values:raise ValueError('existing card/input/answers changed; new version required')
                    continue
                db.execute('INSERT INTO cards VALUES(?,?,?,?,?,?)',values)
                db.execute('INSERT INTO reviews(card_id) VALUES(?)',(row['id'],))

    def session(self):
        with connect(self.path) as db:return json.loads(db.execute('SELECT value FROM review_session WHERE id=1').fetchone()[0])

    def set_session(self,value):
        if not isinstance(value,dict) or not set(value)<={'current','filter','status','search','hold'}:
            raise ValueError('invalid session')
        if any(not isinstance(v,str) or len(v)>1000 for v in value.values()):raise ValueError('invalid session value')
        with connect(self.path) as db:db.execute('UPDATE review_session SET value=? WHERE id=1',(dumps(value),))

    def queue(self):
        with connect(self.path) as db:
            rows=db.execute('SELECT c.id,c.kind,c.required,c.body,r.status,r.revision,r.revealed FROM cards c JOIN reviews r ON r.card_id=c.id ORDER BY c.rowid').fetchall()
        bundle=self.translation_bundle();translations={e['source']:e['ru'] for e in bundle['entries']} if bundle else {}
        resolutions=self.resolutions()
        return [dict(id=r['id'],kind=r['kind'],required=bool(r['required']) and r['status']!='confirmed' and not (r['id'] in resolutions),
                     status='accepted' if r['status']=='pending' and r['id'] in resolutions else r['status'],
                     trusted_source=resolutions[r['id']]['source'] if r['id'] in resolutions else None,
                     revision=r['revision'],revealed=bool(r['revealed']),title=json.loads(r['body']).get('title'),
                     title_ru=translations.get(json.loads(r['body']).get('title')),
                     episode_id=json.loads(r['body']).get('episode_id')) for r in rows]

    def card(self,rid):
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            c=db.execute('SELECT * FROM cards WHERE id=?',(rid,)).fetchone()
            r=db.execute('SELECT * FROM reviews WHERE card_id=?',(rid,)).fetchone()
            if not c or not r:raise ValueError('unknown card')
            r=dict(r)
            if c['kind'] not in {'control','agreement'} and not r['revealed']:
                r['revealed']=1;r['revision']+=1;r['updated_at']=utc()
                db.execute('UPDATE reviews SET revealed=1,revision=?,updated_at=? WHERE card_id=?',
                           (r['revision'],r['updated_at'],rid))
                db.execute('INSERT INTO review_events(card_id,input_hash,action,revision,payload,at) VALUES(?,?,?,?,?,?)',
                           (rid,c['input_hash'],'display_answers',r['revision'],dumps({'revealed':True,'mode':'visible_by_default'}),utc()))
            events=db.execute('SELECT * FROM review_events WHERE card_id=? ORDER BY id',(rid,)).fetchall()
        review=dict(r);review['draft']=json.loads(review['draft']);review['confirmed']=json.loads(review['confirmed']) if review['confirmed'] else None
        resolution=self.resolutions().get(rid) if r['status']=='pending' else None
        answers=json.loads(c['annotations']) if resolution or r['revealed'] or c['kind'] not in {'control','agreement'} else None
        body=json.loads(c['body'])
        rubric=next((a.get('rubric_text') for a in json.loads(c['annotations']) if a.get('rubric_text')),None)
        sources=translation_sources(body,answers)
        if rubric:sources.add(rubric)
        bundle=self.translation_bundle()
        translation={'schema':bundle['schema'],'author':bundle.get('author'),'bundle_sha256':digest(bundle),
            'strings':{e['source']:e['ru'] for e in bundle['entries'] if e['source'] in sources}} if bundle else None
        return {'card':body,'kind':c['kind'],'review':review,'annotations':answers,
                'rubric':rubric,'translation':translation,'trusted_resolution':resolution,
                'scorer_input':body.get('scorer_serialized',input_text(body)),'scorer_question':QUESTION,
                'history':[dict(e,payload=json.loads(e['payload'])) for e in events]}

    def act(self,rid,request):
        action=request.get('action')
        if action not in {'draft','reveal','confirm'}:raise ValueError('invalid action')
        translation_hash=request.get('translation_bundle_sha256')
        if translation_hash is not None:
            bundle=self.translation_bundle()
            if not bundle or translation_hash!=digest(bundle):raise ValueError('translation version changed; reload card')
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM trusted_labels WHERE card_id=?',(rid,)).fetchone():
                raise ValueError('trusted label already accepted; reload the card, preserve this version')
            c=db.execute('SELECT * FROM cards WHERE id=?',(rid,)).fetchone()
            row=db.execute('SELECT * FROM reviews WHERE card_id=?',(rid,)).fetchone()
            if not c or not row:raise ValueError('unknown card')
            r=dict(row)
            if request.get('input_sha256')!=c['input_hash']:raise ValueError('input version changed')
            if request.get('revision')!=r['revision']:raise ValueError('stale revision; reload card')
            draft=json.loads(r['draft'])
            if action=='draft':
                draft=request.get('draft')
                if not isinstance(draft,dict) or set(draft)!={'label','note','disposition','adopted'}:raise ValueError('invalid draft schema')
                if draft['label'] not in LABELS|{None} or draft['disposition'] not in {'decision','deferred','defect'} or draft['adopted'] not in {'independent','deepseek','qwen'}:
                    raise ValueError('invalid draft fields')
                if not isinstance(draft['note'],str) or len(draft['note'])>20000:raise ValueError('invalid note')
                r['status']='draft';r['draft']=dumps(draft)
            elif action=='reveal':
                if c['kind'] in {'control','agreement'} and not r['revealed']:
                    if draft.get('label') not in LABELS:raise ValueError('independent blind label required')
                    r['first_label']=draft['label']
                r['revealed']=1
            else:
                if self.session().get('hold')=='yes':raise ValueError('queue paused for rubric revision')
                if not draft.get('note','').strip():raise ValueError('reason required before confirmation')
                if draft.get('disposition')=='decision':
                    if draft.get('label') not in LABELS:raise ValueError('label required')
                    if c['kind'] in {'control','agreement'} and not r['revealed']:raise ValueError('reveal answers before final confirmation')
                    r['status']='confirmed'
                else:r['status']=draft.get('disposition')
                if r['status'] not in {'confirmed','deferred','defect'}:raise ValueError('invalid disposition')
                r['confirmed']=dumps(draft)
            revision=r['revision']+1
            db.execute('UPDATE reviews SET revision=?,status=?,draft=?,first_label=?,revealed=?,confirmed=?,updated_at=? WHERE card_id=?',
                (revision,r['status'],r['draft'],r['first_label'],r['revealed'],r['confirmed'],utc(),rid))
            db.execute('INSERT INTO review_events(card_id,input_hash,action,revision,payload,at) VALUES(?,?,?,?,?,?)',
                (rid,c['input_hash'],action,revision,dumps({'draft':draft,'first_label':r['first_label'],'revealed':bool(r['revealed']),'status':r['status'],'translation_bundle_sha256':translation_hash}),utc()))
        return self.card(rid)

    def export(self):
        result=[]
        for row in self.queue():
            if row['status']=='accepted':
                value=self.card(row['id'])
                result.append({'schema':'trusted-label-v1','row_id':row['id'],'input_sha256':value['card']['input_sha256'],
                    'card':value['card'],'decision':value['trusted_resolution']['annotation'],'resolution':value['trusted_resolution'],
                    'human_review':False,'llm_annotations':value['annotations']})
                continue
            if row['status']!='confirmed':continue
            value=self.card(row['id']);review=value['review']
            if review['status']!='confirmed':continue
            confirmation=next(e for e in reversed(value['history']) if e['action']=='confirm')
            result.append({'schema':'human-review-v1','row_id':row['id'],'input_sha256':value['card']['input_sha256'],
                'card':value['card'],'decision':review['confirmed'],'human_review':True,
                'first_independent_label':review['first_label'],'answers_revealed':bool(review['revealed']),
                'llm_annotations':value['annotations'],'audit_history':value['history'],
                'translation':value['translation'] if confirmation['payload'].get('translation_bundle_sha256') else None,
                'review_revision':review['revision'],'confirmed_at':review['updated_at']})
        return result

    def backup(self,destination):
        destination=Path(destination)
        destination.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive file creation prevents accidentally replacing an earlier backup.
        with destination.open('xb'):pass
        with sqlite3.connect(self.path) as source,sqlite3.connect(destination) as target:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('backup integrity failed')
        return destination


def import_run(root,db_path,annotation_version=2):
    rows=read_jsonl(root/'queue.jsonl')
    plan=None
    if annotation_version==2:
        plan=json.loads((root/'annotation-plan-v2.json').read_text())
        if plan['annotation_version']!=2 or plan['queue_sha256']!=filehash(root/'queue.jsonl') or plan['row_ids']!=[r['id'] for r in rows]:
            raise ValueError('annotation version/queue differs from frozen plan')
    snaps={r['id']:r for r in read_jsonl(root/'snapshots.jsonl')}
    for row in rows:
        row['diagnostic_history']=snaps[row['snapshot_id']]['history']
        row['included_events']=snaps[row['snapshot_id']]['included_events']
        row['excluded_observed_events']=snaps[row['snapshot_id']]['excluded_observed_events']
    folder=root/('annotations' if annotation_version==1 else 'annotations-v2')
    annotations= {r['id']:[json.loads(p.read_text()) for p in sorted(folder.glob(r['id']+'-*.json'))] for r in rows}
    with connect(BUDGET_DB) as ledger:
        seen_calls=set()
        for row in rows:
            for answer in annotations[row['id']]:
                if answer['call_id'] in seen_calls:raise ValueError('duplicate annotation call')
                seen_calls.add(answer['call_id'])
                call=ledger.execute('SELECT request,request_hash,response FROM api_calls WHERE series=? AND call_id=?',
                                    ((plan or {}).get('series','annotation'),answer['call_id'])).fetchone()
                if not call:raise ValueError('annotation request missing from durable ledger')
                if digest(answer['raw'])!=digest(json.loads(call['response'])):
                    raise ValueError('original annotation response differs from ledger')
                request=json.loads(call['request']);rubric=request['messages'][0]['content']
                if answer['model'] not in {DEEPSEEK,QWEN} or request['model']!=answer['model']:
                    raise ValueError('annotation model differs from paid request')
                tag='deepseek' if answer['model']==DEEPSEEK else 'qwen'
                prefix=(plan or {}).get('namespace','')+('rubric-v1/' if annotation_version==1 else 'rubric-v1/schema-v2/')
                if answer['call_id']!=prefix+row['id']+'/'+tag or answer.get('annotation_version',1)!=annotation_version:
                    raise ValueError('annotation call/version differs from selected series')
                expected_format=annotation_payload(row,answer['model'],rubric,annotation_version)['response_format']
                if request.get('response_format')!=expected_format:
                    raise ValueError('annotation response format differs from selected version')
                if plan and (plan['rubric_sha256']!=answer['rubric_sha256'] or plan['response_format']!=expected_format):
                    raise ValueError('annotation rubric/format differs from frozen plan')
                if hashlib.sha256(rubric.encode()).hexdigest()!=answer['rubric_sha256'] or json.loads(request['messages'][1]['content'])!=row['input']:
                    raise ValueError('annotation prompt/input differs from ledger')
                if answer['status']=='valid':
                    choice=answer['raw']['choices'][0]
                    if validate_annotation(choice['message']['content'],choice['finish_reason'],row['input'])!=answer['annotation']:
                        raise ValueError('parsed annotation differs from original response')
                answer['rubric_text']=rubric
                answer['parameters']={k:v for k,v in request.items() if k!='messages'}
                answer['request_sha256']=call['request_hash']
    store=ReviewStore(db_path);store.import_cards(rows,annotations)
    return store


def serve(store,port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,value,status=200,content_type='application/json'):
            data=value.encode() if isinstance(value,str) else dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type',content_type+'; charset=utf-8')
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
            self.end_headers();self.wfile.write(data)
        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{port}',f'localhost:{port}'}
        def do_GET(self):
            if not self.valid_host():self.send({'error':'invalid host'},403);return
            route=urlparse(self.path)
            try:
                if route.path=='/':self.send(Path(__file__).with_name('review.html').read_text(),content_type='text/html')
                elif route.path=='/api/state':self.send({'queue':store.queue(),'session':store.session()})
                elif route.path=='/api/card':self.send(store.card(parse_qs(route.query)['id'][0]))
                else:self.send({'error':'not found'},404)
            except (ValueError,KeyError) as exc:self.send({'error':str(exc)},400)
        def do_POST(self):
            if not self.valid_host() or self.headers.get('Origin') not in {None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'} or self.headers.get('Content-Type')!='application/json':
                self.send({'error':'invalid local origin/content type'},403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=100000:raise ValueError('invalid request size')
                value=json.loads(self.rfile.read(size))
                if self.path=='/api/act':self.send(store.act(value['id'],value))
                elif self.path=='/api/session':store.set_session(value);self.send({'saved':True})
                elif self.path=='/api/export':
                    folder=store.path.parent/'exports';folder.mkdir(exist_ok=True)
                    target=folder/('review-labels-v1-'+uuid.uuid4().hex+'.jsonl')
                    rows=store.export()
                    with target.open('x') as f:
                        for row in rows:f.write(dumps(row)+'\n')
                    self.send({'path':str(target),'accepted':len(rows),'confirmed':sum(r['human_review'] for r in rows),'schema':'review-labels-v1'})
                elif self.path=='/api/backup':
                    target=store.path.parent/'backups'/('pilot-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite3')
                    store.backup(target)
                    ledger=None
                    if BUDGET_DB.exists() and store.path.resolve()!=BUDGET_DB.resolve():
                        ledger=target.with_name(target.stem+'-budget.sqlite3')
                        with ledger.open('xb'):pass
                        with sqlite3.connect(BUDGET_DB) as source,sqlite3.connect(ledger) as destination:
                            source.backup(destination)
                            if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('budget backup integrity failed')
                    self.send({'path':str(target),'budget_path':str(ledger) if ledger else None,'integrity':'ok'})
                else:self.send({'error':'not found'},404)
            except (ValueError,KeyError,TypeError) as exc:self.send({'error':str(exc)},409)
            except (sqlite3.Error,OSError):self.send({'error':'Ошибка записи SQLite/файла. Изменения не подтверждены; оставайтесь на карточке.'},500)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(dumps({'url':f'http://127.0.0.1:{port}','database':str(store.path),'cards':len(store.queue())}),flush=True)
    server.serve_forever()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=DEFAULT_RUN)
    parser.add_argument('--db',type=Path)
    parser.add_argument('--annotation-version',type=int,choices=[1,2],default=2)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('import')
    p=sub.add_parser('serve');p.add_argument('--port',type=int,default=8765)
    p=sub.add_parser('backup');p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('restore');p.add_argument('--from-backup',type=Path,required=True)
    p=sub.add_parser('export');p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('translations');p.add_argument('--from-file',type=Path,required=True)
    p=sub.add_parser('trust');p.add_argument('--adjudications',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve();db=args.db.resolve() if args.db else root/'pilot.sqlite3'
    if args.command=='restore':
        if db.exists():raise ValueError('restore destination must be new; preserve the current database')
        with sqlite3.connect(f'file:{args.from_backup.resolve()}?mode=ro',uri=True) as source:
            if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('invalid backup')
            db.parent.mkdir(parents=True,exist_ok=True)
            with db.open('xb'):pass
            with sqlite3.connect(db) as destination:source.backup(destination)
        print(db);return
    store=import_run(root,db,args.annotation_version) if args.command=='import' else ReviewStore(db)
    if args.command=='serve':serve(store,args.port)
    elif args.command=='trust':
        store.accept_models(json.loads(args.adjudications.read_text()))
        print(dumps({'accepted':len(store.resolutions()),'human_review':False}))
    elif args.command=='translations':
        bundle=json.loads(args.from_file.read_text());store.import_translations(bundle)
        print(dumps({'strings':len(bundle['entries']),'bundle_sha256':digest(bundle)}))
    elif args.command=='backup':print(store.backup(args.out))
    elif args.command=='export':
        rows=store.export()
        with args.out.open('x') as f:
            for row in rows:f.write(dumps(row)+'\n')
        print(dumps({'path':str(args.out.resolve()),'confirmed':len(rows)}))
    elif args.command=='import':print(dumps({'cards':len(store.queue()),'required':sum(r['required'] for r in store.queue())}))


if __name__=='__main__':main()
