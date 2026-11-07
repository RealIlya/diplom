"""Offline contracts for paid collection, visibility and persistent review."""
import copy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io
from urllib.error import HTTPError

from scripts.system_one_pilot.data import digest
from scripts.system_one_pilot.live_api import BudgetError, PaidClient
from scripts.system_one_pilot.live_data import observed_state, structural_parts, validate_annotation, select_cards
from scripts.system_one_pilot.live import sealed_train_tasks
from scripts.system_one_pilot.review import ReviewStore


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'pilot.sqlite3'
        self.response = {'id': 'gen-test', 'provider': 'DeepSeek', 'choices': [
            {'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'ok'}}],
            'usage': {'prompt_tokens': 2, 'completion_tokens': 2, 'cost': 0.001}}
        self.sent = []

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, transport=None):
        def send(request):
            self.sent.append(copy.deepcopy(request))
            return copy.deepcopy(self.response)
        return PaidClient(self.db, 'collection', transport=transport or send)

    def request(self):
        return {'model': 'deepseek/deepseek-v4.1-flash-1017',
                'messages': [{'role': 'user', 'content': 'hello'}], 'max_tokens': 2048}

    def test_completed_request_is_replayed_after_restart_without_payment(self):
        self.client().complete('episode/agent/0', self.request())
        self.client().complete('episode/agent/0', self.request())
        self.assertEqual(len(self.sent), 1)
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.client().complete('episode/agent/0', dict(self.request(), temperature=.3))

    def test_generation_id_is_journaled_before_response_body_is_read(self):
        checks=[];path=self.db
        class Reply:
            headers={'X-Generation-Id':'gen-before-body','Authorization':'DO NOT STORE SECRET'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):
                with sqlite3.connect(path) as db:
                    record=db.execute("SELECT body FROM api_receipts WHERE series='collection' AND call_id='interrupted'").fetchone()
                checks.append(json.loads(record[0]))
                raise TimeoutError('body interrupted')
        with patch('scripts.system_one_pilot.live_api.key',return_value='test-only'),patch('scripts.system_one_pilot.live_api.urllib.request.urlopen',return_value=Reply()):
            client=PaidClient(self.db,'collection')
            with self.assertRaises(BudgetError):client.complete('interrupted',self.request())
        self.assertEqual(checks,[{'generation_id':'gen-before-body'}])
        self.assertEqual(client.summary()['unresolved'],1)
        with self.assertRaises(BudgetError):self.client().complete('interrupted',self.request())
        with sqlite3.connect(self.db) as db:
            with self.assertRaises(sqlite3.IntegrityError):db.execute("DELETE FROM api_receipts")

    def test_unknown_outcome_holds_reserve_and_blocks_series(self):
        def timeout(request):
            raise TimeoutError('DO NOT LOG SECRET')
        with self.assertRaisesRegex(BudgetError, 'unknown'):
            self.client(timeout).complete('x', self.request())
        with self.assertRaisesRegex(BudgetError, 'unknown'):
            self.client().complete('y', self.request())
        with sqlite3.connect(self.db) as db:
            state, held, error = db.execute('SELECT status,reserved_nusd,error FROM api_calls').fetchone()
        self.assertEqual(state, 'unknown')
        self.assertGreater(held, 0)
        self.assertNotIn('SECRET', error)
        self.assertEqual(len(self.sent), 0)

    def test_no_request_can_exceed_separate_persistent_budget(self):
        request = self.request()
        request['messages'][0]['content'] = 'x' * 4_000_000
        with self.assertRaises(BudgetError):
            self.client().complete('too-big', request)
        self.assertEqual(self.sent, [])
        self.client().complete('one', self.request())
        self.assertAlmostEqual(self.client().summary()['actual_usd'], .001)
        other = PaidClient(self.db, 'annotation', transport=lambda r:self.response)
        self.assertEqual(other.summary()['actual_usd'], 0)
        self.assertEqual(other.summary()['limit_usd'], .5)

    def test_missing_usage_keeps_maximum_and_disables_followup(self):
        self.response['usage'] = {}
        self.client().complete('x', self.request())
        with self.assertRaises(BudgetError):
            self.client().complete('y', self.request())

    def test_definite_http_rejection_can_be_accounted_at_full_bound_without_repaying(self):
        def reject(request):
            raise HTTPError('https://openrouter.ai/api/v1/chat/completions',404,'DO NOT LOG SECRET',{},
                            io.BytesIO(b'{"error":{"message":"No matching endpoint","code":404}}'))
        client=self.client(reject)
        with self.assertRaises(BudgetError):client.complete('rejected',self.request())
        held=client.summary()['charged_or_held_usd']
        client.account_rejected_bound('rejected',{'reason':'HTTP 404, key usage receipt unchanged; charge maximum conservatively'})
        self.assertEqual(client.summary()['charged_or_held_usd'],held)
        self.assertEqual(client.summary()['unresolved'],0)
        with self.assertRaises(BudgetError):self.client().complete('rejected',self.request())
        self.client().complete('diagnostic-different-call',self.request())
        self.assertAlmostEqual(self.client().summary()['charged_or_held_usd'],held+.001)
        with sqlite3.connect(self.db) as db:
            response=db.execute("SELECT response FROM api_calls WHERE call_id='rejected'").fetchone()[0]
        self.assertIn('No matching endpoint',response)
        self.assertNotIn('SECRET',response)

    def test_investigated_upstream_overload_keeps_full_bound_and_never_retries_call(self):
        body={'error':{'message':'Provider returned error','code':429,'metadata':{'provider_name':'DeepInfra','provider_error_code':'engine_overloaded','limit_source':'upstream_provider_shared_pool'}}}
        def reject(request):raise HTTPError('https://openrouter.ai/api/v1/chat/completions',429,'overload',{},io.BytesIO(json.dumps(body).encode()))
        client=self.client(reject)
        with self.assertRaises(BudgetError):client.complete('overloaded',self.request())
        held=client.summary()['charged_or_held_usd']
        with sqlite3.connect(self.db) as db:raw=json.loads(db.execute("SELECT response FROM api_calls WHERE call_id='overloaded'").fetchone()[0])
        with self.assertRaises(BudgetError):client.account_rejected_bound('overloaded',{'reason':'unbound assertion'})
        client.account_rejected_bound('overloaded',{'reason':'inspected explicit pre-inference shared-pool rejection; retain full bound','response_sha256':digest(raw)})
        self.assertEqual(client.summary()['charged_or_held_usd'],held)
        self.assertEqual(client.summary()['unresolved'],0)
        with self.assertRaises(BudgetError):self.client().complete('overloaded',self.request())
        self.client().complete('next-unstarted-task',self.request())
        self.assertEqual(len(self.sent),1)

    def test_generic_429_cannot_be_reconciled_by_asserting_overload(self):
        def reject(request):raise HTTPError('https://openrouter.ai/api/v1/chat/completions',429,'generic',{},io.BytesIO(b'{"error":{"code":429}}'))
        client=self.client(reject)
        with self.assertRaises(BudgetError):client.complete('unknown429',self.request())
        with sqlite3.connect(self.db) as db:raw=json.loads(db.execute("SELECT response FROM api_calls WHERE call_id='unknown429'").fetchone()[0])
        with self.assertRaises(BudgetError):client.account_rejected_bound('unknown429',{'reason':'not proven pre-inference','response_sha256':digest(raw)})
        self.assertEqual(client.summary()['unresolved'],1)

    def test_http_status_survives_failure_while_reading_error_body(self):
        class BrokenBody(io.BytesIO):
            def read(self,*args):raise TimeoutError('DO NOT LOG SECRET')
        def reject(request):raise HTTPError('https://openrouter.ai/api/v1/chat/completions',404,'error',{},BrokenBody())
        client=self.client(reject)
        with self.assertRaises(BudgetError):client.complete('broken-error-body',self.request())
        client.account_rejected_bound('broken-error-body',{'reason':'known HTTP404, unavailable body, retain entire bound'})
        self.assertEqual(client.summary()['unresolved'],0)

    def test_discount_free_reservation_covers_utf8_tools_and_output(self):
        client = self.client()
        client.complete('x', self.request())
        request = self.sent[0]
        self.assertFalse(request['provider']['allow_fallbacks'])
        self.assertEqual(request['provider']['only'], ['deepinfra/fp8'])
        with sqlite3.connect(self.db) as db:
            reserved, bound = db.execute('SELECT reserved_nusd,input_bound FROM api_calls').fetchone()
        self.assertGreaterEqual(bound, len(json.dumps(request,ensure_ascii=False).encode()))
        self.assertGreaterEqual(reserved / 1e9, bound * .3e-6 + 2048 * 1.2e-6)

    def test_changing_run_root_does_not_reset_authorized_series_budget(self):
        from scripts.system_one_pilot import live
        self.client().complete('existing-call',self.request())
        for name in ['run-one','run-two']:
            output=io.StringIO()
            with patch.object(live,'BUDGET_DB',self.db), patch('sys.argv',['live','--root',str(Path(self.tmp.name)/name),'budget']),redirect_stdout(output):
                live.main()
            value=json.loads(output.getvalue())
            self.assertAlmostEqual(value['collection']['actual_usd'],.001)


class DataTests(unittest.TestCase):
    def test_report_keeps_technical_errors_out_of_labels_and_counts_unknown_cost_bound(self):
        from scripts.system_one_pilot.report import annotation_summary,cost_summary
        rows=[{'row_id':'r','model':'A','status':'valid','annotation':{'label':'useful'}},
              {'row_id':'r','model':'B','status':'technical_error','error':'bad JSON','annotation':{'label':'uncertain'}}]
        report=annotation_summary(rows)
        self.assertEqual(report['valid_labels'],{'useful':1})
        self.assertEqual(report['pairs_with_two_valid_answers'],0)
        cost=cost_summary([{'response':None,'reserved_nusd':1000,'actual_nusd':None},
                           {'response':json.dumps({'usage':{'cost':.000002}}),'reserved_nusd':4000,'actual_nusd':2000}])
        self.assertEqual(cost['reported_usage_cost_usd_exact'],'0.000002')
        self.assertEqual(cost['budget_charged_or_held_usd'],.000003)
        self.assertEqual(cost['unknown_actual_cost_calls'],1)

    def test_report_invalid_raw_cost_remains_unknown_at_full_reservation(self):
        from scripts.system_one_pilot.report import cost_summary
        for invalid in [-.001, '0.001', True, float('nan'), float('inf')]:
            with self.subTest(cost=invalid):
                report=cost_summary([{'response':json.dumps({'usage':{'cost':invalid}}),
                    'reserved_nusd':10000,'actual_nusd':None}])
                self.assertEqual(report['reported_usage_cost_usd_exact'],'0')
                self.assertEqual(report['unknown_actual_cost_calls'],1)
                self.assertEqual(report['budget_charged_or_held_usd'],.00001)
    def test_strict_annotation_payload_is_independent_and_versioned(self):
        from scripts.system_one_pilot.live import annotation_payload
        from scripts.system_one_pilot.live_api import DEEPSEEK,QWEN
        row={'input':{'state':'current need','candidate':'evidence'},'other_answer':'SECRET OTHER MODEL'}
        a=annotation_payload(row,DEEPSEEK,'rubric',2)
        b=annotation_payload(row,QWEN,'rubric',2)
        self.assertEqual(a['messages'],b['messages'])
        self.assertNotIn('SECRET OTHER MODEL',json.dumps(a))
        self.assertEqual(a['response_format']['type'],'json_schema')
        self.assertTrue(a['response_format']['json_schema']['strict'])
        self.assertFalse(a['response_format']['json_schema']['schema']['additionalProperties'])
        self.assertEqual(annotation_payload(row,DEEPSEEK,'rubric',1)['response_format']['type'],'json_object')
    def test_reproducibility_manifest_keeps_source_and_marks_absent_packages_unknown(self):
        from scripts.system_one_pilot import live
        import importlib.metadata
        with tempfile.TemporaryDirectory(dir=live.ROOT) as tmp,patch.object(live,'BASE',Path(tmp)),patch.object(live.importlib.metadata,'version',side_effect=importlib.metadata.PackageNotFoundError):
            value=live.code_manifest()
            self.assertTrue(all(v is None for v in value['versions'].values()))
            self.assertTrue((Path(tmp)/'code-snapshots').is_dir())

    @unittest.skipUnless(os.environ.get('SYSTEM_ONE_NATIVE_TESTS') == '1',
                         'Native tests require SYSTEM_ONE_NATIVE_TESTS=1 and pinned source data')
    def test_collection_selection_is_sealed_train_and_distinct_families(self):
        root = Path(__file__).resolve().parents[1]
        source = next((root/'artifacts/system-one-pilot/source').glob('tau2-*'))
        selected = sealed_train_tasks(source)
        split = json.loads((root/'experiments/system-one-pilot/manifests-v3/split.json').read_text())
        self.assertEqual(len(selected),5)
        self.assertEqual(len({split['tasks'][t]['family'] for t in selected}),5)
        self.assertTrue(all(split['tasks'][t]['split']=='train' for t in selected))

    def messages(self):
        return [
            {'role':'system','content':'HIDDEN_POLICY'},
            {'role':'assistant','content':'What would you like?'},
            {'role':'user','content':'cash back', 'raw_data':{'hidden':'SECRET'}},
            {'role':'assistant','tool_calls':[{'id':'kb','name':'KB_search','arguments':{'query':'cash back'}}]},
            {'role':'tool','requestor':'assistant','id':'kb','content':'1. Rewards\n   ID: r\n   Score: 1.0\n   Content: Rules\n\nExcept premium.\n\n'} ,
            {'role':'assistant','tool_calls':[{'id':'b','name':'get_balance','arguments':{'account':'1'}}]},
            {'role':'tool','requestor':'assistant','id':'b','content':'100'},
            {'role':'user','tool_calls':[{'id':'s'}],'content':'SIMULATOR'},
            {'role':'tool','requestor':'user','id':'s','content':'HIDDEN'},
            {'role':'user','content':'FUTURE'}]

    def test_context_contract_no_future_hidden_or_kb_body_in_state(self):
        result = observed_state(self.messages(), 9)
        state = json.loads(result['state'])
        self.assertEqual(state['search_context']['arguments']['query'], 'cash back')
        self.assertEqual(state['tool_events'][0]['content'], '100')
        for text in ['HIDDEN', 'SECRET', 'SIMULATOR', 'FUTURE', 'Except premium']:
            self.assertNotIn(text, result['state'])
        self.assertIn('Except premium', result['pool'][0]['content'])
        self.assertEqual(result, observed_state(self.messages(), 9))

    def test_observed_tool_status_and_failed_search_are_not_lost_or_documents(self):
        messages=self.messages()[:7]
        messages[-1]['error']=True
        messages += [{'role':'assistant','tool_calls':[{'id':'bad','name':'KB_search','arguments':{'query':'x'}}]},
                     {'role':'tool','requestor':'assistant','id':'bad','content':'backend failed','error':True}]
        value=observed_state(messages,len(messages));state=json.loads(value['state'])
        self.assertTrue(state['tool_events'][0]['error'])
        self.assertEqual(state['search_context']['outcome'],'error')
        self.assertIn('backend failed',state['search_context']['error_content'])
        self.assertEqual(len(value['pool']),1)

    def test_structural_parts_preserve_conditions_spans_and_whole_short_document(self):
        doc = 'Introduction.\n\n# Terms\n\nGeneral rule.\n\nExcept premium customers.\n\n# Examples\n\nExample one.\n\nExample two.'
        whole = structural_parts(doc, lambda s:True)
        self.assertEqual(whole, [{'text':doc,'spans':[[0,len(doc)]]}])
        parts = structural_parts(doc, lambda s:len(s)<110)
        self.assertTrue(parts)
        for part in parts:
            self.assertIn('Except premium customers.',part['text'])
            self.assertIn('Introduction.',part['text'])
            self.assertEqual(part['text'], '\n\n'.join(doc[a:b] for a,b in part['spans']))
        self.assertIsNone(structural_parts('x'*1000, lambda s:len(s)<20))

    def test_structural_split_keeps_assumptions_with_numeric_evidence(self):
        text='Savings.\n\n# Estimates\n\n$10k earns $200/year.\n\nThese estimates assume the APY remains the same and the balance does not change.\n\n# Other\n\nUnrelated explanatory example.'
        parts=structural_parts(text,lambda t:len(t)<len(text)-10)
        self.assertTrue(parts)
        for part in parts:
            if '$200/year' in part['text']:self.assertIn('assume the APY',part['text'])

    def test_annotation_schema_literal_quotes_and_finish_are_required(self):
        payload = {'label':'useful','reason':'applies','conditions':'standard card',
                   'defect':False,'quotes':[{'source':'candidate','text':'cash back'}]}
        inputs = {'state':'cash back wanted','candidate':'cash back rule'}
        self.assertEqual(validate_annotation(json.dumps(payload),'stop',inputs)['label'],'useful')
        for value,finish in [(payload,'length'),(dict(payload,quotes=[{'source':'candidate','text':'FAKE'}]),'stop'),
                             (dict(payload,label='maybe'),'stop'),(dict(payload,defect='false'),'stop')]:
            with self.assertRaises(ValueError):validate_annotation(json.dumps(value),finish,inputs)

    def test_selection_caps_episode_and_round_robins_snapshots(self):
        rows=[{'id':str(i),'episode_id':str(i//20),'snapshot_id':str(i//5),'admission':'accepted'} for i in range(100)]
        selected=select_cards(rows)
        self.assertEqual(len(selected),30)
        self.assertEqual(selected,select_cards(rows))
        from collections import Counter
        self.assertLessEqual(max(Counter(r['episode_id'] for r in selected).values()),10)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.sqlite3'
        self.row={'id':'r','input':{'state':'s','candidate':'c'},'episode_id':'e','snapshot_id':'snap',
                  'representation':'v1','source_spans':[[0,1]],'provenance':[], 'title':'Title', 'document_id':'doc'}
        self.row['input_sha256']=digest(self.row['input'])
        self.annotations=[{'status':'valid','input_sha256':self.row['input_sha256'],'row_id':'r',
            'model':model,'rubric_sha256':'rubric-test','annotation':{'label':'useful','reason':'rule','defect':False},
            'raw':{'secret_answer':'yes'}} for model in ['deepseek','qwen']]
        self.store=ReviewStore(self.path)
        self.store.import_cards([self.row],{'r':self.annotations},control_seed=25)

    def tearDown(self):self.tmp.cleanup()

    def act(self,action,**kw):
        r=self.store.card('r')['review']
        return self.store.act('r',{'action':action,'revision':r['revision'],
            'input_sha256':self.row['input_sha256'],**kw})

    def test_import_binds_distinct_models_calls_and_strict_version_to_paid_requests(self):
        import hashlib
        from scripts.system_one_pilot import review
        from scripts.system_one_pilot.live import annotation_payload
        from scripts.system_one_pilot.live_api import DEEPSEEK,QWEN
        root=Path(self.tmp.name)/'run';root.mkdir();folder=root/'annotations-v2';folder.mkdir()
        row=self.row;rubric='test rubric';rubric_hash=hashlib.sha256(rubric.encode()).hexdigest()
        (root/'queue.jsonl').write_text(json.dumps(row)+'\n')
        (root/'snapshots.jsonl').write_text(json.dumps({'id':'snap','history':[],
            'included_events':[],'excluded_observed_events':[]})+'\n')
        from scripts.system_one_pilot.cli import filehash
        (root/'annotation-plan-v2.json').write_text(json.dumps({'annotation_version':2,
            'queue_sha256':filehash(root/'queue.jsonl'),'row_ids':['r'],'rubric_sha256':rubric_hash,
            'response_format':annotation_payload(row,DEEPSEEK,rubric,2)['response_format']}))
        ledger=Path(self.tmp.name)/'ledger.sqlite3'
        annotation={'label':'useful','reason':'rule','conditions':'none','defect':False,
                    'quotes':[{'source':'candidate','text':'c'}]}
        raw={'choices':[{'message':{'content':json.dumps(annotation)},'finish_reason':'stop'}],
             'usage':{'cost':.000001}}
        records=[]
        for model,tag in [(DEEPSEEK,'deepseek'),(QWEN,'qwen')]:
            call_id='rubric-v1/schema-v2/r/'+tag
            PaidClient(ledger,'annotation',transport=lambda request:raw).complete(
                call_id,annotation_payload(row,model,rubric,2))
            records.append({'row_id':'r','input_sha256':row['input_sha256'],'rubric_sha256':rubric_hash,
                'annotation_version':2,'model':model,'call_id':call_id,'raw':raw,'status':'valid',
                'annotation':validate_annotation(json.dumps(annotation),'stop',row['input'])})
        def save(records):
            for record,tag in zip(records,['deepseek','qwen']):
                (folder/('r-'+tag+'.json')).write_text(json.dumps(record))
        with patch.object(review,'BUDGET_DB',ledger):
            save(records)
            self.assertEqual(len(review.import_run(root,root/'valid.sqlite3').queue()),1)
            duplicate=copy.deepcopy(records);duplicate[1]=dict(duplicate[0],model=QWEN)
            save(duplicate)
            with self.assertRaisesRegex(ValueError,'model|call'):
                review.import_run(root,root/'duplicate.sqlite3')
            save(records)
            # A genuine v1 ledger response cannot be relabelled as v2 on disk.
            old_call='rubric-v1/r/qwen'
            PaidClient(ledger,'annotation',transport=lambda request:raw).complete(
                old_call,annotation_payload(row,QWEN,rubric,1))
            records[1]['call_id']=old_call;save(records)
            with self.assertRaisesRegex(ValueError,'version|call|format'):
                review.import_run(root,root/'wrong-version.sqlite3')

    def test_blind_reveal_draft_session_confirmation_restart_and_export(self):
        self.assertIsNone(self.store.card('r')['annotations'])
        with self.assertRaises(ValueError):self.act('reveal')
        self.act('draft',draft={'label':'useful','note':'my own reason','disposition':'decision','adopted':'independent'})
        self.store.set_session({'current':'r','filter':'all','status':'pending'})
        self.store=ReviewStore(self.path)
        self.assertEqual(self.store.session()['current'],'r')
        self.assertEqual(self.store.card('r')['review']['draft']['note'],'my own reason')
        self.act('reveal')
        self.assertEqual(self.store.card('r')['review']['first_label'],'useful')
        self.assertIsNotNone(self.store.card('r')['annotations'])
        self.assertEqual(self.store.export(),[])
        self.act('confirm')
        self.assertEqual(self.store.export()[0]['decision']['label'],'useful')
        self.act('draft',draft={'label':'irrelevant','note':'correction','disposition':'decision','adopted':'independent'})
        self.act('confirm')
        self.assertEqual(self.store.card('r')['review']['first_label'],'useful')
        self.assertEqual(self.store.export()[0]['decision']['label'],'irrelevant')
        self.assertEqual(sum(e['action']=='confirm' for e in self.store.card('r')['history']),2)

    def test_stale_revision_and_changed_input_cannot_overwrite_decisions(self):
        request={'action':'draft','revision':0,'input_sha256':self.row['input_sha256'],
                 'draft':{'label':'uncertain','note':'need data','disposition':'decision','adopted':'independent'}}
        self.store.act('r',request)
        with self.assertRaisesRegex(ValueError,'revision'):self.store.act('r',request)
        with self.assertRaises(ValueError):self.store.act('r',dict(request,revision=1,input_sha256='changed'))
        changed=copy.deepcopy(self.row);changed['input']['candidate']='new';changed['input_sha256']=digest(changed['input'])
        with self.assertRaises(ValueError):self.store.import_cards([changed],{'r':self.annotations})

    def test_annotation_for_different_input_cannot_enter_review_queue(self):
        store=ReviewStore(Path(self.tmp.name)/'other.sqlite3')
        answers=copy.deepcopy(self.annotations)
        answers[0]['input_sha256']='different-input'
        with self.assertRaisesRegex(ValueError,'annotation input'):
            store.import_cards([self.row],{'r':answers})

    def test_russian_translation_persists_without_changing_input_or_revealing_blind_answers(self):
        from scripts.system_one_pilot.review import translation_sources
        answers=copy.deepcopy(self.annotations)
        for answer in answers:answer['annotation'].update(reason='SECRET model rationale',conditions='Only when eligible',
            quotes=[{'source':'candidate','text':'c'}])
        store=ReviewStore(Path(self.tmp.name)/'translated.sqlite3');store.import_cards([self.row],{'r':answers})
        sources=translation_sources(self.row,answers)
        bundle={'schema':'review-ru-v1','author':'Codex','created_at':'2026-10-25',
                'entries':[{'source':s,'source_sha256':__import__('hashlib').sha256(s.encode()).hexdigest(),
                            'ru':'Перевод '+s} for s in sorted(sources)]}
        before=store.card('r');store.import_translations(bundle)
        value=store.card('r')
        self.assertEqual(value['card'],before['card']);self.assertEqual(value['review'],before['review'])
        self.assertIsNone(value['annotations'])
        self.assertNotIn('SECRET model rationale',json.dumps(value))
        self.assertEqual(value['translation']['strings']['c'],'Перевод c')
        self.assertEqual(store.queue()[0]['title_ru'],'Перевод Title')
        store.import_translations(bundle)  # exact replay is safe
        altered=copy.deepcopy(bundle);altered['entries'][0]['ru']='changed'
        with self.assertRaisesRegex(ValueError,'immutable|changed'):store.import_translations(altered)
        self.store=store
        self.act('draft',draft={'label':'useful','note':'моё решение','disposition':'decision','adopted':'independent'})
        self.act('reveal');self.act('confirm',translation_bundle_sha256=digest(bundle))
        self.assertIn('SECRET model rationale',store.card('r')['translation']['strings'])
        backup=Path(self.tmp.name)/'translated-backup.sqlite3';store.backup(backup)
        exported=ReviewStore(backup).export()[0]
        self.assertEqual(exported['translation']['bundle_sha256'],digest(bundle))
        self.assertEqual(exported['card']['input_sha256'],self.row['input_sha256'])

    def test_translation_import_rejects_incomplete_unknown_and_wrong_hash_sources(self):
        from scripts.system_one_pilot.review import translation_sources
        import hashlib
        bundle={'schema':'review-ru-v1','author':'Codex','created_at':'2026-10-25','entries':[
            {'source':s,'source_sha256':hashlib.sha256(s.encode()).hexdigest(),'ru':'Перевод '+s}
            for s in translation_sources(self.row,self.annotations)]}
        for mutation in ['missing','unknown','wrong_hash','empty']:
            bad=copy.deepcopy(bundle)
            if mutation=='missing':bad['entries'].pop()
            elif mutation=='unknown':bad['entries'].append({'source':'unknown','source_sha256':hashlib.sha256(b'unknown').hexdigest(),'ru':'неизвестно'})
            elif mutation=='wrong_hash':bad['entries'][0]['source_sha256']='wrong'
            else:bad['entries'][0]['ru']=' '
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.store.import_translations(bad)

    def test_trusted_models_accept_consensus_and_agent_arbitration_without_human_labels(self):
        from scripts.system_one_pilot.live_api import DEEPSEEK,QWEN
        store=ReviewStore(Path(self.tmp.name)/'trusted.sqlite3')
        rows=[];annotations={}
        for rid in ['agreement','disagreement']:
            row=dict(self.row,id=rid);rows.append(row)
            answers=copy.deepcopy(self.annotations)
            for a,model in zip(answers,[DEEPSEEK,QWEN]):a.update(row_id=rid,model=model,call_id=rid+'/'+model)
            if rid=='disagreement':answers[1]['annotation']['label']='irrelevant'
            annotations[rid]=answers
        store.import_cards(rows,annotations)
        with self.assertRaisesRegex(ValueError,'agent'):store.accept_models({})
        self.assertEqual(store.resolutions(),{})  # whole batch is transactional
        override={'input_sha256':self.row['input_sha256'],'reason_ru':'Применимое исключение; частичная полезность достаточна.',
            'annotation':{'label':'useful','reason':'Applicable exception','conditions':'none','defect':False,
                          'quotes':[{'source':'candidate','text':'c'}]}}
        store.accept_models({'disagreement':override})
        store.accept_models({'disagreement':override})
        self.assertTrue(all(r['status']=='accepted' and not r['required'] for r in store.queue()))
        value=store.card('agreement')
        for action in ['draft','reveal','confirm']:
            with self.subTest(action=action),self.assertRaisesRegex(ValueError,'already accepted'):
                store.act('agreement',{'action':action,'revision':value['review']['revision'],
                    'input_sha256':self.row['input_sha256'],'draft':{
                        'label':'irrelevant','note':'stale tab','disposition':'decision','adopted':'independent'}})
        self.assertIsNotNone(value['annotations']);self.assertIsNone(value['review']['first_label'])
        self.assertEqual(value['review']['status'],'pending')  # original human review is untouched
        exported=store.export();self.assertEqual(len(exported),2)
        self.assertTrue(all(r['human_review'] is False for r in exported))
        self.assertEqual({r['resolution']['source'] for r in exported},{'llm_consensus','agent_adjudication'})
        bad=copy.deepcopy(override);bad['annotation']['label']='uncertain'
        with self.assertRaises(ValueError):store.accept_models({'disagreement':bad})
        backup=Path(self.tmp.name)/'trusted-backup.sqlite3';store.backup(backup)
        self.assertEqual(ReviewStore(backup).export(),exported)

    def test_trusted_resolution_preserves_existing_human_draft(self):
        from scripts.system_one_pilot.live_api import DEEPSEEK,QWEN
        store=ReviewStore(Path(self.tmp.name)/'draft-trusted.sqlite3')
        answers=copy.deepcopy(self.annotations)
        for a,m in zip(answers,[DEEPSEEK,QWEN]):a['model']=m
        store.import_cards([self.row],{'r':answers});self.store=store
        self.act('draft',draft={'label':'irrelevant','note':'мой черновик','disposition':'decision','adopted':'independent'})
        before=store.card('r')['review'];store.accept_models({})
        self.assertEqual(store.card('r')['review'],before)
        self.assertEqual(store.resolutions(),{})

    def test_nonblind_visible_answers_are_recorded_as_revealed(self):
        store=ReviewStore(Path(self.tmp.name)/'conflict.sqlite3')
        answers=copy.deepcopy(self.annotations);answers[1]['annotation']['label']='irrelevant'
        store.import_cards([self.row],{'r':answers})
        value=store.card('r')
        self.assertIsNotNone(value['annotations'])
        self.assertTrue(value['review']['revealed'])

    def test_defer_defect_and_uncertain_are_distinct_backup_is_restorable(self):
        for disposition in ['deferred','defect']:
            self.act('draft',draft={'label':None,'note':'diagnostic','disposition':disposition,'adopted':'independent'})
            self.act('confirm')
            self.assertEqual(self.store.card('r')['review']['status'],disposition)
            self.assertEqual(self.store.export(),[])
        self.act('draft',draft={'label':'uncertain','note':'not enough observed data','disposition':'decision','adopted':'independent'})
        self.act('reveal');self.act('confirm')
        backup=Path(self.tmp.name)/'backup.sqlite3';self.store.backup(backup)
        restored=ReviewStore(backup)
        self.assertEqual(restored.export()[0]['decision']['label'],'uncertain')
        with sqlite3.connect(self.path) as db:
            with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE cards SET annotations='[]'")


if __name__ == '__main__':
    unittest.main()
