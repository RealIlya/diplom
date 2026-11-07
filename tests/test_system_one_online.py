import copy
import os
from contextlib import closing
import unittest
from scripts.system_one_pilot import online

class CharacterTokenizer:
    def encode(self,text,add_special_tokens=False):return list(text)

class ContinuationTests(unittest.TestCase):
    def prior(self, folder):
        import json
        from scripts.system_one_pilot.live_api import DEEPSEEK
        receipt={'arm':'frozen','protocol_sha256':'p','dataset_sha256':'d','evaluation':'ALL',
                 'actor':DEEPSEEK,'simulator':DEEPSEEK,'judge':DEEPSEEK,
                 'head_sha256':'h','tasks':['task_035','task_061','task_041'],
                 'episodes':[{'task_id':'task_035','status':'completed'},
                             {'task_id':'task_061','status':'failed'}]}
        (folder/'receipt.json').write_text(json.dumps(receipt))
        for task,status in [('task_035','completed'),('task_061','failed')]:
            (folder/(task+'.json')).write_text(json.dumps({'task_id':task,'status':status,
                'arm':'frozen','episode_id':'online-adaptation-v1/frozen/'+task,'native':{}}))
        (folder/'selector-events.jsonl').write_text('')
    def test_continuation_retains_failed_attempt_and_only_leaves_unstarted_task(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);self.prior(folder)
            receipt,records,events=online.load_prior(folder,'frozen','p','d',
                ['task_035','task_061','task_041'],'h')
            self.assertEqual(records['task_061']['status'],'failed')
            self.assertEqual([t for t in receipt['tasks'] if t not in records],['task_041'])
            self.assertEqual(events,'')
    def test_continuation_rejects_changed_lineage_or_unrecorded_paid_attempt(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);self.prior(folder)
            with self.assertRaisesRegex(ValueError,'lineage'):
                online.load_prior(folder,'frozen','CHANGED','d',['task_035','task_061','task_041'],'h')
            (folder/'task_061.json').unlink()
            with self.assertRaisesRegex(ValueError,'attempt'):
                online.load_prior(folder,'frozen','p','d',['task_035','task_061','task_041'],'h')

class OnlineTests(unittest.TestCase):
    def pool(self):return [{'candidate_id':'a','document_id':'a','title':'A','content':'rule one'},
                           {'candidate_id':'b','document_id':'b','title':'B','content':'rule two'}]
    def test_packer_keeps_whole_observed_candidates_and_counts_full_render(self):
        tok=CharacterTokenizer();pool=self.pool();text=online.evidence_text([pool[0]])
        selected,rendered=online.pack_evidence(pool,['a','b'],tok,len(text))
        self.assertEqual(selected,['a']);self.assertEqual(rendered,text)
        with self.assertRaisesRegex(ValueError,'candidate'):online.pack_evidence(pool,['hidden'],tok,10000)
        with self.assertRaisesRegex(ValueError,'duplicate'):online.pack_evidence(pool,['a','a'],tok,10000)
    def test_projection_preserves_policy_tools_non_kb_and_error_outcomes(self):
        raw=[{'role':'assistant','content':None,'tool_calls':[{'id':'kb','name':'KB_search','arguments':{'query':'q'}}]},
             {'role':'tool','id':'kb','requestor':'assistant','content':'SECRET_RAW_KB','error':False},
             {'role':'assistant','content':None,'tool_calls':[{'id':'db','name':'get_balance','arguments':{}}]},
             {'role':'tool','id':'db','requestor':'assistant','content':'balance=50','error':False},
             {'role':'assistant','content':None,'tool_calls':[{'id':'err','name':'KB_search','arguments':{'query':'q2'}}]},
             {'role':'tool','id':'err','requestor':'assistant','content':'retrieval failed','error':True}]
        before=copy.deepcopy(raw);projected=online.project_messages(raw,'ONLY_SELECTED_EVIDENCE')
        self.assertEqual(raw,before);self.assertEqual(projected[3],raw[3]);self.assertEqual(projected[5],raw[5])
        self.assertEqual(projected[0],raw[0]);self.assertIn('ONLY_SELECTED_EVIDENCE',projected[1]['content'])
        self.assertNotIn('SECRET_RAW_KB',str(projected))
    def test_local_failure_calls_accounted_llm_fallback_and_invalid_llm_keeps_bm25(self):
        calls=[]
        def llm(state,pool):calls.append('llm');return ['b']
        def fail(row):raise ValueError('overflow')
        ids,events=online.select_evidence('frozen','observed',self.pool(),fail,llm)
        self.assertEqual(ids,['b']);self.assertEqual(calls,['llm']);self.assertIn('local_error',events)
        def invalid(state,pool):return ['future-gold']
        ids,events=online.select_evidence('llm','observed',self.pool(),None,invalid)
        self.assertEqual(ids,['a','b']);self.assertIn('invalid_llm_ids',events)
    def test_empty_local_selection_uses_fallback_and_ties_are_stable(self):
        pool=self.pool()
        ids,events=online.select_evidence('ce','s',pool,lambda row:.1,lambda s,p:['b'])
        self.assertEqual(ids,['b']);self.assertIn('empty_local_selection',events)
        ids,events=online.select_evidence('brier','s',pool,lambda row:.8,lambda s,p:[])
        self.assertEqual(ids,['a','b'])

if __name__=='__main__':unittest.main()

@unittest.skipUnless(os.environ.get('SYSTEM_ONE_NATIVE_TESTS') == '1',
                     'Native tests require SYSTEM_ONE_NATIVE_TESTS=1 and the pinned pilot environment')
class NativeJudgeBoundaryTests(unittest.TestCase):
    def test_native_default_judge_is_routed_to_declared_model_and_paid_ledger(self):
        import json
        import os
        from pathlib import Path
        import sqlite3
        import sys
        import tempfile
        from scripts.system_one_pilot.live import TAU,native_transport
        from scripts.system_one_pilot.live_api import PaidClient,DEEPSEEK
        sys.path.insert(0,str(TAU/'src'));os.environ['TAU2_DATA_DIR']=str(TAU/'data');os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
        import tau2.utils.llm_utils as llm
        sent=[]
        def transport(payload):
            sent.append(payload)
            return {'id':'fake-local','model':DEEPSEEK,'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':'{"results":[]}'}}],
                    'usage':{'prompt_tokens':10,'completion_tokens':5,'cost':.00001}}
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'ledger.sqlite3';client=PaidClient(db,'collection',transport)
            with native_transport(client,'test-only-online',allow_judge=True):
                llm.completion(model='unapproved-native-default',messages=[{'role':'user','content':'judge-only criteria'}])
            self.assertEqual(sent[0]['model'],DEEPSEEK)
            with closing(sqlite3.connect(db)) as c:
                cid,payload=c.execute('SELECT call_id,request FROM api_calls').fetchone()
            self.assertTrue(cid.endswith('/judge'));self.assertEqual(json.loads(payload)['model'],DEEPSEEK)

@unittest.skipUnless(os.environ.get('SYSTEM_ONE_NATIVE_TESTS') == '1',
                     'Native tests require SYSTEM_ONE_NATIVE_TESTS=1 and the pinned pilot environment')
class NativeProjectionTests(unittest.TestCase):
    def test_real_native_agent_keeps_raw_trajectory_but_sends_only_selected_kb(self):
        import json
        import os
        from pathlib import Path
        import sys
        import tempfile
        from scripts.system_one_pilot.live import TAU,native_transport,sealed_train_tasks
        from scripts.system_one_pilot.live_api import PaidClient,DEEPSEEK
        from scripts.system_one_pilot.live_data import observed_state
        sys.path.insert(0,str(TAU/'src'));os.environ['TAU2_DATA_DIR']=str(TAU/'data');os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
        from loguru import logger
        logger.remove()
        from tau2.domains.banking_knowledge.environment import get_environment
        from tau2.user.user_simulator import UserSimulator
        from tau2.data_model.tasks import Task
        from tau2.orchestrator.orchestrator import Orchestrator
        task_id=sealed_train_tasks(TAU)[0];task=Task.model_validate_json((TAU/'data/tau2/domains/banking_knowledge/tasks'/(task_id+'.json')).read_text());env=get_environment(retrieval_variant='bm25')
        def selector(raw):
            snap=observed_state(raw,len(raw))
            if not snap['pool']:return raw
            return online.project_messages(raw,online.evidence_text([snap['pool'][0]]))
        agent=online.selecting_agent(selector)(env.get_tools(),env.get_policy(),DEEPSEEK,{'pilot_role':'agent','num_retries':0})
        user=UserSimulator(instructions=str(task.user_scenario),tools=None,llm=DEEPSEEK,llm_args={'pilot_role':'simulator','num_retries':0})
        messages=[{'role':'assistant','content':'What is your cash back policy?'},
                  {'role':'assistant','content':None,'tool_calls':[{'id':'kb-test','type':'function','function':{'name':'KB_search','arguments':'{"query":"cash back"}'}}]},
                  {'role':'assistant','content':'Here is the policy.'},{'role':'assistant','content':'###STOP###'}]
        sent=[]
        def transport(payload):
            sent.append(payload);message=messages.pop(0)
            return {'id':'fake-local','model':DEEPSEEK,'choices':[{'index':0,'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop','message':message}],
                    'usage':{'prompt_tokens':100,'completion_tokens':20,'cost':.0001}}
        with tempfile.TemporaryDirectory() as d:
            client=PaidClient(Path(d)/'ledger.sqlite3','collection',transport)
            orchestrator=Orchestrator(domain='banking_knowledge',agent=agent,user=user,environment=env,task=task,max_steps=12,seed=25)
            with native_transport(client,'test-only-projection'):result=orchestrator.run()
        raw=[m.model_dump(mode='json') for m in result.messages]
        original=next(m['content'] for m in raw if m['role']=='tool')
        projected=next(m['content'] for m in sent[2]['messages'] if m['role']=='tool')
        self.assertGreater(len(original),len(projected));self.assertIn('Selected observed evidence:',projected)
        self.assertEqual(sent[1]['tools'],sent[2]['tools']);self.assertEqual(sent[1]['messages'][0],sent[2]['messages'][0])
        self.assertNotIn(task.user_scenario.instructions,str(sent[2]['messages']))

class OnlineSummaryTests(unittest.TestCase):
    def test_summary_keeps_failed_and_missing_tasks_and_full_cost(self):
        import json
        from pathlib import Path
        import tempfile
        from types import SimpleNamespace
        from scripts.system_one_pilot.live_api import PaidClient,DEEPSEEK
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=root/'ce';run.mkdir();ledger=root/'ledger.sqlite3'
            client=PaidClient(ledger,'collection',lambda p:{'choices':[{'finish_reason':'stop','message':{'content':'ok'}}],
                            'usage':{'cost':.0001,'prompt_tokens':100,'completion_tokens':10}})
            for tail in ['001/agent','selector/1','002/judge']:
                client.complete('online-adaptation-v1/ce/a/'+tail,{'model':DEEPSEEK,'messages':[{'role':'user','content':'fixture'}],'max_tokens':20})
            (run/'receipt.json').write_text(json.dumps({'arm':'ce','evaluation':'ALL','tasks':['a','b','c'],
                'protocol_sha256':'p','dataset_sha256':'d','setup_seconds':1.}))
            (run/'a.json').write_text(json.dumps({'task_id':'a','status':'completed','elapsed_seconds':2.,'native':{'reward_info':{'reward':1.}}}))
            (run/'b.json').write_text(json.dumps({'task_id':'b','status':'failed','elapsed_seconds':3.,'native':{}}))
            (run/'selector-events.jsonl').write_text(json.dumps({'events':['local_error'],'selector_seconds':.2,'packed_tokens':10})+'\n')
            summary=online.summarize_runs([run],ledger)
            arm=summary['arms']['ce'];self.assertEqual(arm['planned_tasks'],3);self.assertEqual(arm['successes'],1)
            self.assertEqual(arm['failed_tasks'],['b']);self.assertEqual(arm['missing_tasks'],['c'])
            self.assertAlmostEqual(arm['api_actual_usd'],.0003);self.assertEqual(arm['api_calls_by_role'],{'agent':1,'selector':1,'judge':1})
            self.assertEqual(arm['fallback_events']['local_error'],1)
            receipt=json.loads((run/'receipt.json').read_text());receipt['evaluation']='ENV';(run/'receipt.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,'ALL'):online.summarize_runs([run],ledger)

@unittest.skipUnless(os.environ.get('SYSTEM_ONE_NATIVE_TESTS') == '1',
                     'Native tests require SYSTEM_ONE_NATIVE_TESTS=1 and the pinned pilot environment')
class JudgeCompletenessTests(unittest.TestCase):
    def test_empty_partial_or_duplicate_judge_assertions_never_become_success(self):
        import json
        from pathlib import Path
        import tempfile
        from types import SimpleNamespace
        from scripts.system_one_pilot.live import native_transport
        from scripts.system_one_pilot.live_api import PaidClient,DEEPSEEK
        online.bootstrap()
        from tau2.evaluator.evaluator_nl_assertions import NLAssertionsEvaluator
        task=SimpleNamespace(evaluation_criteria=SimpleNamespace(nl_assertions=['must A','must B']))
        a={'expectedOutcome':'must A','metExpectation':True,'reasoning':'fixture'}
        b={'expectedOutcome':'must B','metExpectation':True,'reasoning':'fixture'}
        with tempfile.TemporaryDirectory() as d:
            for i,results in enumerate([[],[a],[a,a],[a,b]]):
                def response(payload):return {'id':'fake-local','model':DEEPSEEK,'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps({'results':results})}}],
                    'usage':{'prompt_tokens':10,'completion_tokens':5,'cost':.00001}}
                client=PaidClient(Path(d)/'ledger.sqlite3','collection',response)
                with native_transport(client,'test-only-judge-'+str(i),allow_judge=True):
                    if i<3:
                        with self.assertRaisesRegex(ValueError,'assertion'):NLAssertionsEvaluator.calculate_reward(task,[])
                    else:self.assertEqual(NLAssertionsEvaluator.calculate_reward(task,[]).reward,1.)

@unittest.skipUnless(os.environ.get('SYSTEM_ONE_NATIVE_TESTS') == '1',
                     'Native tests require SYSTEM_ONE_NATIVE_TESTS=1 and the pinned pilot environment')
class OnlineStopTests(unittest.TestCase):
    def test_reserve_refusal_stops_online_before_next_task(self):
        import json
        from pathlib import Path
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.system_one_pilot import adaptation,live,live_api
        from transformers import AutoTokenizer
        class ExhaustedClient:
            def __init__(self,path,series):self.path=Path(path)
            def summary(self):return {'unresolved':0,'charged_or_held_usd':.9}
            def complete(self,*args):raise live_api.BudgetError('persistent series budget exhausted before HTTP')
        protocol=live.ROOT/'experiments/system-one-pilot/results/adaptation-20261025/protocol.json'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);dataset=root/'data';dataset.mkdir();(dataset/'manifest.json').write_text(json.dumps({'gates_passed':True,'dataset_sha256':'d'}))
            with patch.object(live_api,'preflight',return_value={}),patch.object(live_api,'PaidClient',ExhaustedClient),patch.object(live,'BUDGET_DB',root/'ledger.sqlite3'),patch.object(live,'code_manifest',return_value={}),patch.object(AutoTokenizer,'from_pretrained',return_value=CharacterTokenizer()):
                with self.assertRaises(live_api.BudgetError):online.run(SimpleNamespace(arm='native',protocol=protocol,dataset=dataset,heads=root,out=root/'run'))
            self.assertEqual(len(list((root/'run').glob('task_*.json'))),1)
