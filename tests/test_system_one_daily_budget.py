"""Shared daily reservation across roles, restart and timezone boundaries."""
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from scripts.system_one_pilot import live_api as api


class DailyBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'budget.sqlite3'
        self.req={'model':api.DEEPSEEK,'messages':[{'role':'user','content':'hello'}],'max_tokens':2048}
        self.response={'id':'g','choices':[{'finish_reason':'stop','message':{'content':'ok'}}],
                       'usage':{'cost':.001}}

    def policy(self,cap=5_000_000):
        configure=getattr(api,'configure_daily_budget',None)
        self.assertIsNotNone(configure,'shared daily policy is missing')
        configure(self.db,cap,'Asia/Novosibirsk')

    def test_roles_share_cap_and_completed_replay_is_free(self):
        self.policy();sent=[]
        def send(r):sent.append(r);return copy.deepcopy(self.response)
        a=api.PaidClient(self.db,'collection',send);b=api.PaidClient(self.db,'annotation',send)
        with patch.object(api,'utc',return_value='2026-10-27T00:00:00+00:00'):
            a.complete('a',self.req);a.complete('a',self.req)
            b.complete('b',self.req)
            with self.assertRaisesRegex(api.BudgetError,'daily'):
                a.complete('c',self.req)
            self.assertEqual(api.daily_summary(self.db)['charged_or_held_usd'],.002)
        self.assertEqual(len(sent),2)

    def test_local_midnight_and_existing_calls_are_counted(self):
        a=api.PaidClient(self.db,'collection',lambda r:copy.deepcopy(self.response))
        with patch.object(api,'utc',return_value='2026-10-26T17:00:00+00:00'):
            a.complete('old',self.req)
        self.policy(4_000_000)
        with patch.object(api,'utc',return_value='2026-10-27T16:59:59+00:00'):
            with self.assertRaisesRegex(api.BudgetError,'daily'):a.complete('too-soon',self.req)
            self.assertEqual(api.daily_summary(self.db)['date'],'2026-10-27')
        with patch.object(api,'utc',return_value='2026-10-27T17:00:00+00:00'):
            a.complete('tomorrow',self.req)
            self.assertEqual(api.daily_summary(self.db)['date'],'2026-10-28')
            self.assertEqual(api.daily_summary(self.db)['calls'],1)

    def test_unknown_in_one_role_blocks_other_role_on_next_day(self):
        self.policy(1_000_000_000)
        def timeout(r):raise TimeoutError()
        with patch.object(api,'utc',return_value='2026-10-26T12:00:00+00:00'):
            with self.assertRaises(api.BudgetError):api.PaidClient(self.db,'collection',timeout).complete('x',self.req)
            summary=api.daily_summary(self.db)
            self.assertGreater(summary['charged_or_held_usd'],0)
        with patch.object(api,'utc',return_value='2026-10-27T12:00:00+00:00'):
            with self.assertRaisesRegex(api.BudgetError,'unknown'):
                api.PaidClient(self.db,'annotation',lambda r:self.response).complete('y',self.req)

    def test_policy_and_series_authorizations_cannot_be_raised_on_restart(self):
        self.policy()
        api.authorize_series(self.db,'packet-annotation',750_000_000)
        api.authorize_series(self.db,'packet-annotation',750_000_000)
        self.assertEqual(api.PaidClient(self.db,'packet-annotation').summary()['limit_usd'],.75)
        with self.assertRaises(ValueError):api.authorize_series(self.db,'packet-annotation',1_000_000_000)
        with self.assertRaises(ValueError):api.authorize_series(self.db,'annotation',1_000_000_000)
        with self.assertRaises(ValueError):api.configure_daily_budget(self.db,6_000_000,'Asia/Novosibirsk')
        with sqlite3.connect(self.db) as db:
            with self.assertRaises(sqlite3.IntegrityError):db.execute('DELETE FROM api_daily_policy')

    def test_concurrent_roles_cannot_spend_same_last_reserve(self):
        self.policy();entered=threading.Event();release=threading.Event()
        def slow(r):entered.set();release.wait(5);return copy.deepcopy(self.response)
        a=api.PaidClient(self.db,'collection',slow)
        b=api.PaidClient(self.db,'annotation',lambda r:copy.deepcopy(self.response))
        with ThreadPoolExecutor(max_workers=1) as executor:
            job=executor.submit(a.complete,'a',self.req)
            self.assertTrue(entered.wait(5))
            try:
                with self.assertRaises(api.BudgetError):b.complete('b',self.req)
            finally:release.set()
            job.result()
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM api_calls').fetchone()[0],1)


if __name__=='__main__':unittest.main()
