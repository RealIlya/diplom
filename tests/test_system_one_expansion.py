"""Train-only expansion preserves group identity and excludes previous labels."""
import importlib.util
import unittest
from pathlib import Path
import tempfile
import json
from types import SimpleNamespace
from unittest.mock import patch


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        global expansion
        self.assertIsNotNone(importlib.util.find_spec('scripts.system_one_pilot.expansion'),'expansion pipeline missing')
        expansion=importlib.import_module('scripts.system_one_pilot.expansion')

    def test_task_plan_prefers_unrepresented_train_families_and_never_test(self):
        m={'tasks':{'a':{'split':'train','family':'old'},'b':{'split':'train','family':'new'},
                    'c':{'split':'train','family':'new'},'d':{'split':'dev','family':'dev'},
                    't':{'split':'test','family':'test'}}}
        p=expansion.task_plan(m,{'old'})
        self.assertEqual(len(p),1);self.assertIn(p[0],['b','c'])
        self.assertEqual(p,expansion.task_plan(m,{'old'}))

    def test_queue_excludes_old_inputs_and_document_snapshot_variants(self):
        def row(i,**kw):
            return dict(id=str(i),input_sha256='h'+str(i),snapshot_id='s'+str(i),document_id='d',
                        split='train',family='f',admission='accepted',**kw)
        old=row(0);variant=dict(row(1),snapshot_id='s0');copy_input=dict(row(2),input_sha256='h0')
        dev=dict(row(3),split='dev');test=dict(row(4),split='test')
        rows=[old,variant,copy_input,dev,test,row(5),row(5),row(6)]
        selected=expansion.choose_new_cards(rows,[old],target=20)
        self.assertEqual({r['id'] for r in selected},{'5','6'})

    def test_family_round_robin_prevents_one_pool_consuming_target(self):
        rows=[dict(id=str(i),input_sha256='h'+str(i),snapshot_id='s'+str(i),document_id='d',
                   split='train',family='a' if i<10 else 'b',admission='accepted') for i in range(12)]
        self.assertEqual({r['family'] for r in expansion.choose_new_cards(rows,[],target=2)},{'a','b'})

    def test_fresh_pairs_take_priority_over_cached_families(self):
        def row(i,family):return dict(id=str(i),input_sha256=str(i),snapshot_id=str(i),document_id='d',split='train',family=family,admission='accepted')
        choose=getattr(expansion,'choose_packet_cards',None)
        self.assertIsNotNone(choose,'fresh priority missing')
        rows=choose([row(i,'new') for i in range(200)],[row(i,'old') for i in range(200,400)],[],200)
        self.assertEqual(len(rows),200);self.assertEqual({r['family'] for r in rows},{'new'})

    def test_saved_queue_resume_validates_hash_without_reextracting(self):
        resume=getattr(expansion,'existing_queue',None)
        self.assertIsNotNone(resume,'queue resume missing')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);report=root/'report';report.mkdir()
            queue=root/'queue.jsonl';queue.write_text('{}\n')
            (report/'queue-summary.json').write_text(json.dumps({'queue_sha256':expansion.filehash(queue)}))
            self.assertTrue(resume(root,report))
            queue.write_text('{"changed":true}\n')
            with self.assertRaises(ValueError):resume(root,report)

    def test_selected_snapshots_resolve_cached_and_fresh_sources(self):
        merge=getattr(expansion,'selected_snapshots',None)
        self.assertIsNotNone(merge,'cached snapshot provenance missing')
        snapshots=merge([{'id':'fresh','history':[]}],[{'id':'old','history':[]},{'id':'dev','history':[]}],
                        [{'snapshot_id':'fresh'},{'snapshot_id':'old'}])
        self.assertEqual({s['id'] for s in snapshots},{'fresh','old'})
        with self.assertRaises(ValueError):merge([],[],[{'snapshot_id':'missing'}])

    def test_merge_labels_preserves_old_roles_and_keeps_uncertain_out_of_hard_rows(self):
        from scripts.system_one_pilot.data import digest
        merge=getattr(expansion,'merge_labeled',None)
        self.assertIsNotNone(merge,'versioned dataset merge missing')
        old={'id':'old','role':'validation','task_id':'d','split':'dev','family':'dev',
             'snapshot_id':'s0','document_id':'doc','input':{'state':'old','candidate':'text'}}
        old['input_sha256']=digest(old['input'])
        card=dict(old,id='new',task_id='t',split='train',family='train',snapshot_id='s1',
                  input={'state':'new','candidate':'text'})
        card.pop('role');card['input_sha256']=digest(card['input'])
        label={'row_id':'new','input_sha256':card['input_sha256'],'card':card,
               'decision':{'label':'uncertain','defect':False},'resolution':{'source':'agent_adjudication'}}
        manifest={'tasks':{'d':{'split':'dev','family':'dev'},'t':{'split':'train','family':'train'}}}
        merged=merge([old],[label],manifest)
        self.assertEqual(merged[0],old)
        self.assertEqual(merged[1]['role'],'train');self.assertEqual(merged[1]['label'],'uncertain')
        self.assertEqual(merged[1]['label_source'],'agent_adjudication')
        self.assertEqual(old['role'],'validation')

    def test_merge_labels_rejects_duplicate_inputs_and_snapshot_document_variants(self):
        from scripts.system_one_pilot.data import digest
        merge=getattr(expansion,'merge_labeled',None)
        self.assertIsNotNone(merge,'versioned dataset merge missing')
        old={'id':'old','role':'train','task_id':'t','split':'train','family':'f',
             'snapshot_id':'s','document_id':'d','input':{'state':'old','candidate':'text'}}
        old['input_sha256']=digest(old['input']);manifest={'tasks':{'t':{'split':'train','family':'f'}}}
        card=dict(old,id='new');card.pop('role')
        def label(c):return {'row_id':c['id'],'input_sha256':c['input_sha256'],'card':c,
                            'decision':{'label':'useful','defect':False},'resolution':{'source':'llm_consensus'}}
        with self.assertRaises(ValueError):merge([old],[label(dict(card,snapshot_id='other'))],manifest)
        card['input']={'state':'changed','candidate':'text'};card['input_sha256']=digest(card['input'])
        with self.assertRaises(ValueError):merge([old],[label(card)],manifest)
        with self.assertRaises(ValueError):merge([], [label(dict(card,split='test'))],manifest)
        with self.assertRaises(ValueError):merge([], [label(dict(card,input_sha256='changed'))],manifest)

    def test_new_annotation_series_imports_through_paid_provenance_and_trusted_policy(self):
        from scripts.system_one_pilot import live,live_api,review
        from scripts.system_one_pilot.data import digest
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);db=root/'ledger.sqlite3';split=root/'split.json'
            split.write_text(json.dumps({'tasks':{'t':{'split':'train','family':'f'}}}))
            row={'id':'a','task_id':'t','split':'train','family':'f','title':'A','snapshot_id':'old',
                 'input':{'state':'need','candidate':'evidence'}}
            row['input_sha256']=digest(row['input'])
            (root/'queue.jsonl').write_text(json.dumps(row)+'\n')
            (root/'snapshots.jsonl').write_text(json.dumps({'id':'old','history':[],'included_events':[],'excluded_observed_events':[]})+'\n')
            answer={'label':'useful','reason':'helps','conditions':'','defect':False,
                    'quotes':[{'source':'candidate','text':'evidence'}]}
            raw={'id':'g','choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer)}}],
                 'usage':{'cost':.001}}
            live_api.configure_daily_budget(db,1_000_000_000,'Asia/Novosibirsk')
            live_api.authorize_series(db,'packet',750_000_000)
            factory=lambda path,series:live_api.PaidClient(path,series,lambda request:raw)
            with patch.object(live,'BUDGET_DB',db),patch.object(live,'SPLIT',split),patch.object(live,'preflight',return_value={}),patch.object(live,'PaidClient',side_effect=factory):
                live.annotate(SimpleNamespace(root=root,version=2,series='packet',namespace='new/'))
            with patch.object(review,'BUDGET_DB',db):
                store=review.import_run(root,root/'review.sqlite3')
                store.accept_models({})
                self.assertEqual(store.resolutions()['a']['source'],'llm_consensus')

    def test_resuming_packet_calls_annotation_without_collection_or_extraction(self):
        from scripts.system_one_pilot import live,live_api
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);root=home/'packet';root.mkdir();report=home/'report';report.mkdir()
            base=home/'artifacts/system-one-pilot/adaptation-v1';(base/'dataset-v1').mkdir(parents=True)
            (base/'dataset-v1/dataset.jsonl').write_text('[]');(base/'pool.jsonl').write_text('[]')
            (root/'queue.jsonl').write_text('{}\n')
            (report/'queue-summary.json').write_text(json.dumps({'queue_sha256':expansion.filehash(root/'queue.jsonl')}))
            p={'root':'packet','old_dataset_sha256':expansion.filehash(base/'dataset-v1/dataset.jsonl'),
               'cached_pool_sha256':expansion.filehash(base/'pool.jsonl'),'daily_limit_nusd':1_000_000_000,
               'timezone':'Asia/Novosibirsk','series_caps_nusd':{'expansion-v1-annotation':750_000_000},'tasks':[]}
            (report/'protocol.json').write_text(json.dumps(p));seen=[]
            with patch.object(live,'ROOT',home),patch.object(live,'BUDGET_DB',home/'ledger.sqlite3'),patch.object(live_api,'preflight',return_value={}),patch.object(live,'collect',side_effect=AssertionError('collection must not run')),patch.object(live,'extract',side_effect=AssertionError('extraction must not run')),patch.object(live,'annotate',side_effect=lambda args:seen.append((args.series,args.namespace))):
                expansion.run(SimpleNamespace(root=root,report=report))
            self.assertEqual(seen,[('expansion-v1-annotation','expansion-v1/')])


if __name__=='__main__':unittest.main()
