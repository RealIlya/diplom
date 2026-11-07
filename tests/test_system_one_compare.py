"""Frozen comparison must not silently change cohorts or inflate quality n."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from contextlib import redirect_stdout
import io
import os
from scripts.system_one_pilot import compare
from scripts.system_one_pilot.data import digest

class ComparisonTests(unittest.TestCase):
    def test_cohort_hash_duplicates_and_uncertain(self):
        rows = [{'row_id':str(i),'input_sha256':digest({'state':'s','candidate':str(i)}),
                 'card':{'id':str(i),'input':{'state':'s','candidate':str(i)},'family':'f'},
                 'decision':{'label':label}} for i,label in enumerate(['useful','irrelevant','uncertain'])]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cohort.jsonl'
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            protocol={'cohort_sha256':compare.filehash(path),'rows':3,'hard_labels':2,'families':1}
            self.assertEqual(len(compare.load_cohort(path,protocol)),3)
            with self.assertRaisesRegex(ValueError,'hash'):
                compare.load_cohort(path,dict(protocol,cohort_sha256='bad'))
            path.write_text(''.join(json.dumps(r)+'\n' for r in [rows[0],rows[0],rows[2]]))
            with self.assertRaisesRegex(ValueError,'duplicate'):
                compare.load_cohort(path,dict(protocol,cohort_sha256=compare.filehash(path)))
            rows[0]['card']['input']['state']='changed'
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'input'):
                compare.load_cohort(path,dict(protocol,cohort_sha256=compare.filehash(path)))

    def test_request_has_no_gold_or_future_fields(self):
        card={'input':{'state':'observed','candidate':'evidence'},'label':'useful','diagnostic_history':['future']}
        a=compare.request_payload(card)
        card['label']='irrelevant'
        self.assertEqual(a,compare.request_payload(card))
        self.assertEqual(set(a),{'state','questions'})
        self.assertNotIn('future',json.dumps(a))

    def test_tied_auc_f1_and_one_class(self):
        m=compare.quality([1,0,1,0],[.8,.8,.2,.2])
        self.assertEqual(m['roc_auc'],.5)
        self.assertEqual(m['f1'],.5)
        self.assertEqual(m['balanced_accuracy'],.5)
        self.assertIsNone(compare.quality([0],[0])['roc_auc'])
        with self.assertRaises(ValueError):compare.quality([0],[float('nan')])

    def test_errors_missing_and_repeats_do_not_inflate_denominator(self):
        cards=[{'id':str(i),'label':l} for i,l in enumerate(['useful','irrelevant','uncertain'])]
        records=[{'row_id':str(i),'repeat':r,'phase':'measure','status':'ok','probability':p}
                 for r in range(3) for i,p in enumerate([.8,.1,.4])]
        a=compare.arm_quality(cards,records)
        self.assertEqual(a['quality']['n'],2)
        b=compare.arm_quality(cards,[r for r in records if r['row_id']!='1'])
        self.assertEqual(b['quality']['n'],1)
        self.assertEqual(b['coverage'],2/3)
        err={'row_id':'1','repeat':0,'phase':'measure','status':'error'}
        self.assertEqual(compare.arm_quality(cards,[err])['quality'],None)
        self.assertEqual(compare.common_ids({'a':a,'b':b}),['0','2'])
        # A failed first pass cannot be replaced by a more favorable later repeat.
        failed=[r for r in records if not (r['row_id']=='0' and r['repeat']==0)]
        self.assertNotIn('0',compare.arm_quality(cards,failed)['predictions'])

    def test_run_finalizes_receipt_without_overwriting_start(self):
        class Adapter:
            backend='mps';dtype='test';temperature=1.
            def sync(self):pass
            def encode(self,card):return {},[1,2]
            def forward(self,enc):return .4,[0.,1.]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'run'
            rows=[]
            for i in range(30):
                inp={'state':'fixture','candidate':str(i)}
                rows.append({'row_id':str(i),'input_sha256':digest(inp),
                             'card':{'id':str(i),'input':inp,'family':'fixture'},
                             'decision':{'label':'useful'}})
            cohort=root/'cohort.jsonl';cohort.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            protocol=root/'protocol.json';protocol.write_text(json.dumps({
                'cohort_source':'cohort.jsonl','cohort_sha256':compare.filehash(cohort),
                'rows':30,'hard_labels':30,'families':1,'order_seed':25,'performance_repeats':3}))
            with patch.object(compare,'ROOT',root), patch.object(compare,'PROTOCOL',protocol), patch.object(compare.importlib.metadata,'version',return_value='fixture'), patch.object(compare,'Laya',Adapter), patch.object(compare,'swap',return_value='test'), patch.object(compare,'memory',return_value={}), redirect_stdout(io.StringIO()):
                compare.run(SimpleNamespace(arm='laya',out=out))
            self.assertEqual(json.loads((out/'receipt.json').read_text())['status'],'completed')
            self.assertEqual(json.loads((out/'receipt-start.json').read_text())['status'],'running')
            records=[json.loads(s) for s in (out/'records.jsonl').read_text().splitlines()]
            self.assertEqual(sum(r['phase']=='measure' for r in records),90)

    def test_summary_rejects_protocol_mismatch_and_incomplete_completed_run(self):
        protocol={'cohort_sha256':'cohort','performance_repeats':3}
        receipt={'status':'running','cohort_sha256':'cohort','protocol_sha256':compare.filehash(compare.PROTOCOL)}
        with self.assertRaisesRegex(ValueError,'running'):
            compare.validate_run([{'id':'x'}],receipt,[],protocol)
        receipt['status']='completed';receipt['protocol_sha256']='other'
        with self.assertRaisesRegex(ValueError,'protocol'):
            compare.validate_run([{'id':'x'}],receipt,[],protocol)
        receipt['protocol_sha256']=compare.filehash(compare.PROTOCOL)
        records=[{'phase':'admission','row_id':'x','status':'ok'}]
        with self.assertRaisesRegex(ValueError,'incomplete'):
            compare.validate_run([{'id':'x'}],receipt,records,protocol)

    def test_verified_weights_detect_changed_bytes_or_revision(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);target=base/'weights';target.write_bytes(b'pinned')
            receipt=base/'verified.json';receipt.write_text(json.dumps({'repo':'repo','revision':'pin',
                'files':[{'path':str(target),'bytes':6,'sha256':compare.filehash(target)}]}))
            compare.verify_weights(receipt,'repo','pin')
            with self.assertRaisesRegex(ValueError,'revision'):compare.verify_weights(receipt,'repo','other')
            target.write_bytes(b'edited')
            with self.assertRaisesRegex(ValueError,'bytes'):compare.verify_weights(receipt,'repo','pin')

    def test_summary_accepts_relative_cli_run_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();run=root/'run';run.mkdir()
            rows=[]
            for i,label in enumerate(['useful','irrelevant']):
                inp={'state':'q','candidate':str(i)}
                rows.append({'row_id':str(i),'input_sha256':digest(inp),'decision':{'label':label},
                             'card':{'id':str(i),'input':inp,'family':'f','snapshot_id':'s'}})
            cohort=root/'cohort.jsonl';cohort.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            protocol=root/'protocol.json';protocol.write_text(json.dumps({'cohort_source':'cohort.jsonl',
                'cohort_sha256':compare.filehash(cohort),'rows':2,'hard_labels':2,'families':1,'performance_repeats':3}))
            (run/'receipt.json').write_text(json.dumps({'arm':'laya','status':'completed',
                'cohort_sha256':compare.filehash(cohort),'protocol_sha256':compare.filehash(protocol)}))
            records=[{'phase':'admission','row_id':str(i),'status':'ok'} for i in range(2)]
            records += [{'phase':'measure','repeat':r,'row_id':str(i),'status':'ok','probability':p,
                         'tokenize_seconds':.01,'forward_seconds':.1,'request_seconds':.11}
                        for r in range(3) for i,p in enumerate([.8,.2])]
            (run/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            previous=Path.cwd()
            try:
                os.chdir(root)
                with patch.object(compare,'ROOT',root),patch.object(compare,'PROTOCOL',protocol):
                    compare.summarize(SimpleNamespace(runs=[Path('run')],out=root/'summary.json'))
            finally:os.chdir(previous)
            summary=json.loads((root/'summary.json').read_text())
            self.assertEqual(summary['arms']['laya']['run'],'run')
            self.assertEqual(summary['arms']['laya']['quality']['n'],2)

if __name__=='__main__':unittest.main()
