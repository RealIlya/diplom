"""Continue only unstarted work under the explicit first-packet provider504 exception."""
from pathlib import Path
from types import SimpleNamespace
import json
from scripts.system_one_pilot.expansion import run
from scripts.system_one_pilot.provider_timeouts import reconcile_provider_504s
from scripts.system_one_pilot.live import ROOT,BUDGET_DB
from scripts.system_one_pilot.live_api import BudgetError,daily_summary

report=Path(__file__).absolute().parent
approval=report/'provider-504-approval.json'
args=SimpleNamespace(root=ROOT/'artifacts/system-one-pilot/expansion-packet-v1',report=report)
while True:
    reconciled=reconcile_provider_504s(BUDGET_DB,approval)
    print(json.dumps({'reconciled504':reconciled,'daily':daily_summary(BUDGET_DB)}),flush=True)
    try:
        run(args)
        break
    except BudgetError:
        count=reconcile_provider_504s(BUDGET_DB,approval)
        print(json.dumps({'newly_accounted504':count,'daily':daily_summary(BUDGET_DB)}),flush=True)
        if not count:raise
