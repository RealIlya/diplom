"""Independent evidence probabilities, stable identity and strict cardinality."""
import unittest
import importlib.util
from scripts.system_one_pilot import online


class GroupedTests(unittest.TestCase):
    def setUp(self):
        global grouped
        self.assertIsNotNone(importlib.util.find_spec('scripts.system_one_pilot.grouped'),'grouped scorer is missing')
        grouped=importlib.import_module('scripts.system_one_pilot.grouped')

    def test_branch_text_is_not_put_into_shared_state(self):
        payload=grouped.group_payload('need',[{'candidate_id':'a','title':'A','content':'first'},
                                            {'candidate_id':'b','title':'B','content':'second'}])
        self.assertNotIn('first',payload['state'])
        self.assertIn('first',payload['questions']['a']['instructions'])
        self.assertNotIn('second',payload['questions']['a']['instructions'])
        self.assertEqual([q['type'] for q in payload['questions'].values()],['noul','noul'])
        with self.assertRaises(ValueError):grouped.group_payload('need',[{'candidate_id':'a','title':'A','content':'x'}]*2)

    def test_many_useful_and_none_are_valid_not_one_categorical_distribution(self):
        p=grouped.binary_probabilities([[0,2],[0,2],[2,0]])
        self.assertEqual([x>=.5 for x in p],[True,True,False])
        self.assertGreater(sum(p),1)
        for invalid in ([[0,1,2]],[[0,float('nan')]],[]):
            with self.assertRaises(ValueError):grouped.binary_probabilities(invalid)

    def test_selector_uses_grouped_results_in_candidate_order(self):
        class Scorer:
            def score_many(self,state,pool):return [.8,.1,.9]
            def __call__(self,row):raise AssertionError('unexpected scalar path')
        pool=[{'candidate_id':x,'title':x,'content':'text'} for x in ['a','b','c']]
        ids,flags=online.select_evidence('frozen','need',pool,Scorer(),lambda *_:['b'])
        self.assertEqual(ids,['c','a']);self.assertEqual(flags,[])
        class Broken(Scorer):
            def score_many(self,state,pool):return [.8]
        ids,flags=online.select_evidence('frozen','need',pool,Broken(),lambda *_:['b'])
        self.assertEqual(ids,['b']);self.assertIn('local_error',flags)

    def test_groups_include_last_partial_batch_and_allow_empty_pool(self):
        self.assertEqual(list(grouped.candidate_groups(list(range(12)),5)),
                         [[0,1,2,3,4],[5,6,7,8,9],[10,11]])
        self.assertEqual(list(grouped.candidate_groups([],5)),[])
        with self.assertRaises(ValueError):list(grouped.candidate_groups([1],0))

    def test_old_input_batch_keeps_each_candidate_readout_and_tail(self):
        batch=getattr(grouped,'BatchKev',None)
        self.assertIsNotNone(batch,'old-input batch control missing')
        class Logits(list):
            def tolist(self):return list(self)
        class Model:
            def _hidden(self,rows):return rows
            def _logits(self,row,decide,opts):
                return Logits([row[opts[0]],row[opts[1]]])
        class Adapter:
            model=Model()
            def encode(self,row):
                value=int(row['input']['candidate'].rsplit('\n',1)[-1])
                return {'ids':[0,value,9],'decide_idx':[2],'opt_idx':[[0,1]]},[]
        pool=[{'candidate_id':str(i),'title':'A','content':str(i)} for i in range(7)]
        values=batch(Adapter()).score_many('need',pool)
        self.assertEqual(len(values),7)
        self.assertAlmostEqual(values[0],.5)
        self.assertAlmostEqual(values[-1],.9975273768433653)


if __name__=='__main__':unittest.main()
