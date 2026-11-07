"""Read-only ledger/trajectory audit and metadata-only online report."""
import collections
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import statistics

root = Path(__file__).absolute().parents[4]
report = Path(__file__).absolute().parent
base = root/'artifacts/system-one-pilot/adaptation-v1/online'
summary = json.loads((report/'online-summary.json').read_text())
assert summary['all_six_arms_present']
with closing(sqlite3.connect('file:'+str(root/'artifacts/system-one-pilot/authorized-series-20261025.sqlite3')+'?mode=ro', uri=True)) as db:
    db.row_factory = sqlite3.Row
    calls = db.execute("SELECT * FROM api_calls WHERE series='collection' AND call_id LIKE 'online-adaptation-v1/%'").fetchall()
arms = {}
for arm, saved in summary['arms'].items():
    folder = root/Path(saved['run_directory'])
    selected = [c for c in calls if c['call_id'].split('/')[1] == arm]
    by_role = collections.defaultdict(lambda: {'calls': 0, 'actual_usd': 0., 'charged_or_held_usd': 0., 'unknown_actual_calls': 0, 'prompt_tokens': 0, 'cached_prompt_tokens': 0, 'completion_tokens': 0, 'reasoning_tokens': 0})
    for c in selected:
        request = json.loads(c['request'])
        assert request['model'] == 'deepseek/deepseek-v4.1-flash-1017'
        assert request['provider']['only'] == ['deepinfra/fp8']
        role = 'selector' if '/selector/' in c['call_id'] else c['call_id'].rsplit('/', 1)[-1]
        a = by_role[role]; a['calls'] += 1
        a['actual_usd'] += (c['actual_nusd'] or 0)/1e9
        a['charged_or_held_usd'] += (c['actual_nusd'] if c['actual_nusd'] is not None else c['reserved_nusd'])/1e9
        a['unknown_actual_calls'] += c['actual_nusd'] is None
        response = json.loads(c['response'] or '{}'); usage = response.get('usage') or {}
        a['prompt_tokens'] += usage.get('prompt_tokens', 0)
        a['completion_tokens'] += usage.get('completion_tokens', 0)
        a['cached_prompt_tokens'] += (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0)
        a['reasoning_tokens'] += (usage.get('completion_tokens_details') or {}).get('reasoning_tokens', 0)
    assert abs(sum(v['charged_or_held_usd'] for v in by_role.values())-saved['api_charged_or_held_usd']) < 1e-9
    events = [json.loads(s) for s in (folder/'selector-events.jsonl').read_text().splitlines()]
    assert all(0 <= e['packed_tokens'] <= 4096 and len(e['selected']) == len(set(e['selected'])) for e in events)
    tasks = []
    for p in sorted(folder.glob('task_*.json')):
        r = json.loads(p.read_text()); native = r['native']; reward = native.get('reward_info') or {}
        tasks.append({'task': r['task_id'], 'status': r['status'], 'error_type': r.get('error_type'),
                      'wall_seconds': r['elapsed_seconds'], 'termination': native.get('termination_reason'),
                      'reward': reward.get('reward'), 'reward_basis': reward.get('reward_basis'),
                      'reward_breakdown': reward.get('reward_breakdown'),
                      'nl_checks': len(reward.get('nl_assertions') or []), 'messages': len(native.get('messages') or [])})
    common = set(summary['common_completed_tasks'])
    common_calls = [c for c in selected if c['call_id'].split('/')[2] in common]
    paired = {'tasks': sorted(common), 'successes': sum(t['reward'] == 1 for t in tasks if t['task'] in common),
              'wall_seconds_total': sum(t['wall_seconds'] for t in tasks if t['task'] in common),
              'api_actual_usd': sum(c['actual_nusd'] or 0 for c in common_calls)/1e9,
              'api_charged_or_held_usd': sum(c['actual_nusd'] if c['actual_nusd'] is not None else c['reserved_nusd'] for c in common_calls)/1e9}
    arms[arm] = {'cost_and_tokens_by_role': dict(by_role), 'episodes': tasks, 'common_completed_diagnostic': paired,
                 'selector_events': len(events), 'empty_packs': sum(not e['selected'] for e in events),
                 'max_pack_tokens': max((e['packed_tokens'] for e in events), default=None),
                 'selector_seconds_median': statistics.median(e['selector_seconds'] for e in events) if events else None}
result = {'status': 'passed', 'arms': arms, 'online_total_actual_usd': sum(c['actual_nusd'] or 0 for c in calls)/1e9,
          'online_total_charged_or_held_usd': sum(c['actual_nusd'] if c['actual_nusd'] is not None else c['reserved_nusd'] for c in calls)/1e9,
          'all_paid_roles_included': True, 'pack_budget_verified': True,
          'token_scope': 'Sums of known provider-response usage only; incomplete when response is missing. See unknown_actual_calls; missing usage is not a measured zero.',
          'scope': 'metadata only; API actual is known provider usage, held bound is not confirmed expenditure; small dev pilot, one seed'}
with (report/'online-audit.json').open('x') as f:json.dump(result, f, indent=2)
print(json.dumps(result))
