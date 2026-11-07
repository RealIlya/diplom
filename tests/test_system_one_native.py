"""Real pinned runner/retrieval with fake HTTP; requires live-venv dependencies."""
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest

from scripts.system_one_pilot.live import TAU, DEEPSEEK, sealed_train_tasks, native_transport
from scripts.system_one_pilot.live_api import PaidClient
from scripts.system_one_pilot.live_data import observed_state


@unittest.skipUnless(os.environ.get('SYSTEM_ONE_NATIVE_TESTS') == '1',
                     'Native tests require SYSTEM_ONE_NATIVE_TESTS=1 and the pinned pilot environment')
class NativeSmoke(unittest.TestCase):
    def test_real_native_bm25_and_observation_path_without_paid_http(self):
        os.environ['TAU2_DATA_DIR']=str(TAU/'data')
        os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
        sys.path.insert(0,str(TAU/'src'))
        from loguru import logger
        logger.remove()
        from tau2.agent.llm_agent import LLMAgent
        from tau2.user.user_simulator import UserSimulator
        from tau2.domains.banking_knowledge.environment import get_environment
        from tau2.data_model.tasks import Task
        from tau2.orchestrator.orchestrator import Orchestrator
        task_id=sealed_train_tasks(TAU)[0]
        task=Task.model_validate_json((TAU/'data/tau2/domains/banking_knowledge/tasks'/f'{task_id}.json').read_text())
        env=get_environment(retrieval_variant='bm25')
        agent=LLMAgent(env.get_tools(),env.get_policy(),DEEPSEEK,{'pilot_role':'agent','num_retries':0})
        user=UserSimulator(instructions=str(task.user_scenario),tools=None,llm=DEEPSEEK,llm_args={'pilot_role':'simulator','num_retries':0})
        messages=[{'role':'assistant','content':'What is your cash back policy?'},
                  {'role':'assistant','content':None,'tool_calls':[{'id':'kb-test','type':'function','function':{'name':'KB_search','arguments':'{"query":"cash back"}'}}]},
                  {'role':'assistant','content':'Here is the policy.'},
                  {'role':'assistant','content':'###STOP###'}]
        sent=[]
        def transport(payload):
            sent.append(payload)
            message=messages.pop(0)
            return {'id':'gen-test','model':DEEPSEEK,'provider':'DeepSeek','choices':[{'index':0,'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop','message':message}],
                    'usage':{'prompt_tokens':100,'completion_tokens':20,'cost':.0001}}
        with tempfile.TemporaryDirectory() as tmp:
            client=PaidClient(Path(tmp)/'test.sqlite3','collection',transport)
            orchestrator=Orchestrator(domain='banking_knowledge',agent=agent,user=user,environment=env,task=task,max_steps=12,seed=25)
            with native_transport(client,'test-only'):
                result=orchestrator.run()
            raw=[m.model_dump(mode='json') for m in result.messages]
            snaps=[]
            for i in range(1,len(raw)+1):
                try:snaps.append(observed_state(raw,i))
                except ValueError:pass
            self.assertTrue(any(s['pool'] for s in snaps))
            self.assertEqual(len(sent),4)
            self.assertTrue(any('BM25' in str(t) or 'KB_search' in str(t) for t in sent[1]['tools']))
            self.assertNotIn(task.user_scenario.instructions,sent[1]['messages'][0]['content'])


if __name__=='__main__':unittest.main()
