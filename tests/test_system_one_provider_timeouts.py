"""User-approved 504 accounting retains uncertainty and never repays failed calls."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from scripts.system_one_pilot import live_api as api
from scripts.system_one_pilot.data import digest
from scripts.system_one_pilot.compare import filehash


class TimeoutAccountingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'ledger.sqlite3'
        api.configure_daily_budget(self.db,1_000_000_000,'Asia/Novosibirsk')
        self.series='expansion-v1-annotation';api.authorize_series(self.db,self.series,750_000_000)
        p=self.root/'protocol.json';p.write_text(json.dumps({'root':str(self.root),'namespace':'expansion-v1','daily_limit_nusd':1_000_000_000,'series_caps_nusd':{self.series:750_000_000}}))
        self.approval=self.root/'approval.json';self.approval.write_text(json.dumps({'user_authorization':'Учесть полный максимум504, безповтора','protocol_path':str(p),'protocol_sha256':filehash(p),'namespace':'expansion-v1/','series':[self.series],'allowed_code':504,'requires_saved_generation_id':True,'keep_full_reserved_amount':True,'retry_failed_request':False,'daily_limit_usd':1,'other_unknowns_stop':True}))
        self.row={'id':'card','input':{'state':'need','candidate':'evidence'}};self.row['input_sha256']=digest(self.row['input'])
        (self.root/'queue.jsonl').write_text(json.dumps(self.row)+'\n')
        self.request={'model':api.DEEPSEEK,'messages':[{'role':'system','content':'rubric'},{'role':'user','content':api.dumps(self.row['input'])}],'max_tokens':2048}
        self.call='expansion-v1/rubric-v1/schema-v2/card/deepseek'

    def reconcile(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.system_one_pilot.provider_timeouts'),'504 exception missing')
        module=importlib.import_module('scripts.system_one_pilot.provider_timeouts')
        return module.reconcile_provider_504s(self.db,self.approval)

    def failed(self,code=504,with_id=True):
        response={'error':{'code':code,'metadata':{'error_type':'timeout'}}}
        if with_id:response['id']='gen-saved'
        client=api.PaidClient(self.db,self.series,lambda request:response)
        with self.assertRaises(api.BudgetError):client.complete(self.call,self.request)
        return client,response

    def test_full_bound_is_retained_and_original_error_is_immutable(self):
        client,response=self.failed();before=client.summary()['charged_or_held_usd']
        self.assertEqual(self.reconcile(),1)
        self.assertEqual(client.summary()['charged_or_held_usd'],before)
        self.assertEqual(client.summary()['unresolved'],0)
        self.assertEqual(self.reconcile(),0)
        with self.assertRaises(api.BudgetError):client.complete(self.call,self.request)
        with sqlite3.connect(self.db) as db:
            status,actual,body=db.execute('SELECT status,actual_nusd,response FROM api_calls').fetchone()
        self.assertEqual(status,'unreconciled');self.assertIsNone(actual);self.assertEqual(json.loads(body),response)
        record=json.loads((self.root/'annotations-v2/card-deepseek.json').read_text())
        self.assertEqual(record['status'],'technical_error');self.assertNotIn('annotation',record)
        self.assertEqual(record['raw'],response)
        api.authorize_series(self.db,'expansion-v1-collection',200_000_000)
        good={'choices':[{'message':{'content':'ok'}}],'usage':{'cost':.001}}
        api.PaidClient(self.db,'expansion-v1-collection',lambda request:good).complete('expansion-v1/next',self.request)
        self.assertAlmostEqual(api.daily_summary(self.db)['charged_or_held_usd'],before+.001)

    def test_other_status_and_missing_id_are_not_accounted(self):
        client,_=self.failed(code=503)
        self.assertEqual(self.reconcile(),0);self.assertEqual(client.summary()['unresolved'],1)

    def test_504_without_saved_id_remains_blocking(self):
        client,_=self.failed(with_id=False)
        self.assertEqual(self.reconcile(),0);self.assertEqual(client.summary()['unresolved'],1)

    def test_modified_protocol_is_rejected(self):
        self.failed();(self.root/'protocol.json').write_text('{}')
        with self.assertRaises(ValueError):self.reconcile()

    def test_other_namespace_is_not_covered_by_packet_permission(self):
        self.call='other-packet/card/deepseek';client,_=self.failed()
        self.assertEqual(self.reconcile(),0);self.assertEqual(client.summary()['unresolved'],1)

    def test_mismatched_header_generation_id_stays_blocking(self):
        client,_=self.failed()
        with api.connect(self.db) as db:
            db.execute('INSERT INTO api_receipts VALUES(?,?,?,?,?)',(self.series,self.call,'response_headers',api.dumps({'generation_id':'other'}),api.utc()))
        self.assertEqual(self.reconcile(),0);self.assertEqual(client.summary()['unresolved'],1)


if __name__=='__main__':unittest.main()
