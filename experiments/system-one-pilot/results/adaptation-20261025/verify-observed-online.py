"""Reconstruct observed pools from saved trajectories; no model or API calls."""
import json
import os
import argparse
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
from transformers import AutoTokenizer
from scripts.system_one_pilot.data import digest
from scripts.system_one_pilot.live_data import observed_state
from scripts.system_one_pilot.online import evidence_text

root = Path(__file__).absolute().parents[4]
report = Path(__file__).absolute().parent
base = root/'artifacts/system-one-pilot/adaptation-v1/online'
tok = AutoTokenizer.from_pretrained(root/'artifacts/system-one-pilot/kev-comparison-v1/checkpoints/Qwen--Qwen3.5-0.8B-Base', local_files_only=True)
result = {}
parser=argparse.ArgumentParser()
parser.add_argument('--summary',type=Path,default=report/'online-summary.json')
parser.add_argument('--out',type=Path,default=report/'observed-online-verification.json')
args=parser.parse_args()
summary=json.loads(args.summary.read_text())
for arm,saved in summary['arms'].items():
    folder = root/Path(saved['run_directory'])
    receipt = json.loads((folder/'receipt.json').read_text())
    events = [json.loads(s) for s in (folder/'selector-events.jsonl').read_text().splitlines()]
    checked = 0
    for task in receipt['tasks']:
        path = folder/(task+'.json')
        if not path.exists():continue
        record = json.loads(path.read_text())
        task_events = [e for e in events if e['episode_id'] == record['episode_id']]
        if not task_events:continue
        # The agent never receives simulator-internal tool calls/results.
        messages = [m for m in record['native']['messages']
                    if m['role'] == 'assistant' or
                    (m['role'] == 'user' and not m.get('tool_calls')) or
                    (m['role'] == 'tool' and m.get('requestor') == 'assistant')]
        by_hash = {}
        for cutoff in range(1, len(messages)+1):
            try:snap = observed_state(messages, cutoff)
            except ValueError:continue  # A partial tool batch is not an actor boundary.
            key = digest(snap['state'])
            pool = {d['candidate_id']:d for d in snap['pool']}
            if key in by_hash:assert set(pool) == set(by_hash[key])
            by_hash[key] = pool
        for event in task_events:
            assert event['state_sha256'] in by_hash, (arm, task, 'state missing')
            pool = by_hash[event['state_sha256']]
            assert len(pool) == event['pool_size']
            assert set(event['selected']) <= set(pool)
            assert len(event['selected']) == len(set(event['selected']))
            text = evidence_text([pool[cid] for cid in event['selected']]) if event['selected'] else ''
            assert len(tok.encode(text, add_special_tokens=False)) == event['packed_tokens'] <= 4096
            checked += 1
    assert checked == len(events)
    result[arm] = {'checked_events': checked, 'all_selected_ids_observed': True,
                   'full_evidence_render_token_count_verified': True}
with args.out.open('x') as f:
    json.dump({'status': 'passed', 'arms': result, 'all_six_arms_present':summary['all_six_arms_present'],
               'external_calls': 0, 'model_inference': False}, f, indent=2)
print(json.dumps(result))
