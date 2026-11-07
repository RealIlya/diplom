import copy
import math
import unittest
try:
    import torch
except ModuleNotFoundError as exc:
    if exc.name != 'torch':
        raise
    raise unittest.SkipTest('Head tests require torch; use the pilot environment')
from scripts.system_one_pilot import adapt_head

class TinyHead(torch.nn.Module):
    def __init__(self):
        super().__init__();self.q=torch.nn.Linear(3,2);self.k=torch.nn.Linear(3,2)
    def forward(self,h,opts):return self.k(opts)@self.q(h)/math.sqrt(2)

class HeadTests(unittest.TestCase):
    def rows(self):
        return [{'id':'tr','role':'train','label':'useful','defect':False,'family':'t'},
                {'id':'cal','role':'calibration','label':'irrelevant','defect':False,'family':'c'},
                {'id':'val','role':'validation','label':'useful','defect':False,'family':'v'},
                {'id':'uncertain','role':'train','label':'uncertain','defect':False,'family':'t'}]
    def test_binary_brier_is_scalar_and_has_real_gradient(self):
        z=torch.tensor([[0.,0.]],requires_grad=True);y=torch.tensor([1])
        loss=adapt_head.head_loss(z,y,'brier');self.assertEqual(float(loss.detach()),.25)
        loss.backward();self.assertTrue(torch.isfinite(z.grad).all());self.assertGreater(float(z.grad.abs().sum()),0)
    def test_temperature_fit_never_uses_validation_or_train_labels(self):
        rows=self.rows();z={'tr':[0.,100.],'cal':[0.,3.],'val':[0.,-100.],'uncertain':[0.,2.]}
        a=adapt_head.fit_temperature(z,rows,[.5,1,4])
        changed=copy.deepcopy(rows);changed[0]['label']='irrelevant';changed[2]['label']='irrelevant'
        self.assertEqual(a,adapt_head.fit_temperature(z,changed,[.5,1,4]))
        self.assertEqual(a,4)
    def test_optimizer_updates_only_from_hard_nondefect_train_rows(self):
        torch.manual_seed(25);head=TinyHead();initial=copy.deepcopy(head.state_dict())
        features={r['id']:(torch.randn(3),torch.randn(2,3)) for r in self.rows()}
        config={'epochs':3,'batch_size':2,'seed':25,'lr':.01,'weight_decay':.01}
        curves=adapt_head.train_one(head,self.rows(),features,'ce',config)
        state=copy.deepcopy(head.state_dict());other=TinyHead();other.load_state_dict(initial)
        changed=copy.deepcopy(self.rows());changed[1]['label']='useful';changed[2]['label']='irrelevant'
        changed_features=dict(features);changed_features['cal']=(torch.ones(3)*1000,torch.zeros(2,3));changed_features['val']=(torch.zeros(3),torch.ones(2,3)*1000)
        adapt_head.train_one(other,changed,changed_features,'ce',config)
        self.assertTrue(any(not torch.equal(state[k],initial[k]) for k in state))
        self.assertTrue(all(torch.equal(state[k],other.state_dict()[k]) for k in state))
        self.assertEqual(len(curves),3);self.assertEqual(curves[-1]['train_rows'],1)
    def test_missing_features_are_explicit_coverage_not_negative_predictions(self):
        torch.manual_seed(25);head=TinyHead();features={'tr':(torch.randn(3),torch.randn(2,3))}
        logits,errors=adapt_head.predict(head,self.rows(),features)
        self.assertEqual(set(logits),{'tr'});self.assertEqual(set(errors),{'cal','val','uncertain'})

if __name__=='__main__':unittest.main()
