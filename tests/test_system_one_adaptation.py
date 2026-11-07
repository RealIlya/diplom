import copy
import os
import unittest
from scripts.system_one_pilot import adaptation
from scripts.system_one_pilot.data import digest

class ExpansionTests(unittest.TestCase):
    def manifest(self):
        tasks={f't{i}':{'split':'train','family':f'train{i}'} for i in range(9)}
        tasks.update({f'd{i}':{'split':'dev','family':f'dev{i}'} for i in range(5)})
        tasks['sealed']={'split':'test','family':'test'}
        m={'tasks':tasks,'task_hashes':{k:digest(k) for k in tasks}}
        m['manifest_sha256']=digest(m);return m
    def test_plan_is_deterministic_and_never_reassigns_or_reuses_families(self):
        m=self.manifest();before=copy.deepcopy(m)
        a=adaptation.make_plan(m,['t0'],{'dev0'},train_families=5)
        self.assertEqual(a,adaptation.make_plan(m,['t0'],{'dev0'},train_families=5))
        self.assertEqual(m,before)
        self.assertNotIn('sealed',a['tasks']);self.assertNotIn('t0',a['tasks'])
        self.assertEqual(len(a['calibration_families']),2);self.assertEqual(len(a['validation_families']),3)
        self.assertIn('dev0',a['calibration_families'])
        self.assertFalse(set(a['calibration_families']) & set(a['validation_families']))
        bad=copy.deepcopy(m);bad['tasks']['sealed']['split']='dev'
        with self.assertRaisesRegex(ValueError,'manifest'):adaptation.make_plan(bad,['t0'],{'dev0'})
    def test_sampling_caps_families_with_multiple_episodes_without_labels(self):
        rows=[{'id':f'{family}-{ep}-{i}','family':family,'episode_id':ep,'snapshot_id':str(i%2),
               'admission':'accepted','label':'useful'} for family in ['a','b'] for ep in ['x','y'] for i in range(10)]
        selected=adaptation.select_family_cards(rows,target=12,per_family=6)
        self.assertEqual(len(selected),12)
        self.assertEqual(sum(r['family']=='a' for r in selected),6)
        changed=[dict(r,label='irrelevant') for r in rows]
        self.assertEqual([r['id'] for r in selected],[r['id'] for r in adaptation.select_family_cards(changed,12,6)])
    def test_dataset_rejects_cross_family_or_duplicate_input_leakage(self):
        plan={'calibration_families':['cal'],'validation_families':['val']}
        cards=[{'id':'a','family':'tr','split':'train','input':{'state':'s','candidate':'a'},'label':'useful'},
               {'id':'b','family':'val','split':'dev','input':{'state':'s','candidate':'b'},'label':'irrelevant'}]
        result=adaptation.partition_cards(cards,plan)
        self.assertEqual([r['id'] for r in result['validation']],['b'])
        with self.assertRaisesRegex(ValueError,'overlap'):
            adaptation.partition_cards(cards+[dict(cards[0],id='c',family='val',split='dev')],plan)
        with self.assertRaisesRegex(ValueError,'test'):
            adaptation.partition_cards([dict(cards[0],split='test')],plan)

if __name__=='__main__':unittest.main()

class ExtractionBoundaryTests(unittest.TestCase):
    def test_test_split_is_rejected_before_any_tokenizer_or_files_are_opened(self):
        from scripts.system_one_pilot.live import extract
        from types import SimpleNamespace
        from pathlib import Path
        with self.assertRaisesRegex(ValueError,'test'):
            extract(SimpleNamespace(root=Path('/does-not-exist'),allowed_splits=['test']))

@unittest.skipUnless(os.environ.get('SYSTEM_ONE_NATIVE_TESTS') == '1',
                     'Native tests require SYSTEM_ONE_NATIVE_TESTS=1 and the pinned pilot environment')
class CollectionStopTests(unittest.TestCase):
    def test_reservation_refusal_stops_before_starting_another_episode(self):
        import json
        from pathlib import Path
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.system_one_pilot import live
        from scripts.system_one_pilot.live_api import BudgetError,DEEPSEEK
        class ExhaustedClient:
            def __init__(self,path,series):self.path=Path(path);self.series=series
            def summary(self):return {'unresolved':0,'charged_or_held_usd':.9,'limit_usd':1}
            def complete(self,*args):raise BudgetError('persistent series budget exhausted before HTTP')
        plan={'tasks':['task_007','task_010'],'namespace':'test-only-stop','agent':DEEPSEEK,'simulator':DEEPSEEK}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';db=Path(d)/'ledger.sqlite3'
            with patch.object(adaptation,'verify_collection_plan',return_value=plan),patch.object(live,'preflight',return_value={}),patch.object(live,'PaidClient',ExhaustedClient),patch.object(live,'BUDGET_DB',db),patch.object(live,'code_manifest',return_value={}):
                live.collect(SimpleNamespace(root=root,plan=Path('fixture'),episodes=None))
            self.assertEqual(len(list((root/'trajectories').glob('*.json'))),1)

class SealedSourceTests(unittest.TestCase):
    def test_source_verification_does_not_open_unselected_task_bodies(self):
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from scripts.system_one_pilot import live
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);split=root/'split.json';tasks={};hashes={}
            folder=root/'data/tau2/domains/banking_knowledge/tasks';folder.mkdir(parents=True)
            for i in range(5):
                task_id=f'train{i}';body={'id':task_id}
                tasks[task_id]={'split':'train','family':task_id};hashes[task_id]=digest(body)
                (folder/(task_id+'.json')).write_text(json.dumps(body))
            tasks['unselected']={'split':'test','family':'sealed'};hashes['unselected']='not-opened'
            manifest={'tasks':tasks,'task_hashes':hashes};manifest['manifest_sha256']=digest(manifest)
            split.write_text(json.dumps(manifest))
            (root/'source-manifest.json').write_text(json.dumps({'files':{
                'source.py':'pinned','data/tau2/domains/banking_knowledge/tasks/unselected.json':'not-opened'}}))
            opened=[]
            def expected_hash(path):
                name=str(path.relative_to(root));opened.append(name)
                self.assertEqual(name,'source.py');return 'pinned'
            with patch.object(live,'SPLIT',split),patch.object(live,'filehash',side_effect=expected_hash):
                self.assertEqual(set(live.sealed_train_tasks(root)),{f'train{i}' for i in range(5)})
            self.assertEqual(opened,['source.py'])
