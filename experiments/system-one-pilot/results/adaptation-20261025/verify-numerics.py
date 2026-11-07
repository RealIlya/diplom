"""Independent sklearn/numpy check of saved predictions, without model inference."""
import hashlib
import json
from pathlib import Path
import numpy as np
import sklearn
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, brier_score_loss,
                            confusion_matrix, f1_score, roc_auc_score)

root = Path(__file__).absolute().parents[4]
report = Path(__file__).absolute().parent
base = root / 'artifacts/system-one-pilot/adaptation-v1'
rows = [json.loads(s) for s in (base/'dataset-v1/dataset.jsonl').read_text().splitlines()]
by_id = {r['id']: r for r in rows}
assert len(by_id) == len(rows) == 130
assert {r['role'] for r in rows} == {'train', 'calibration', 'validation'}
families = {role: {r['family'] for r in rows if r['role'] == role}
            for role in ['train', 'calibration', 'validation']}
assert not (families['train'] & families['calibration'] or
            families['train'] & families['validation'] or
            families['calibration'] & families['validation'])
predictions = [json.loads(s) for s in (base/'heads-v1/predictions.jsonl').read_text().splitlines()]
summary = json.loads((base/'heads-v1/summary.json').read_text())
checks = []
max_delta = 0
for arm, saved in summary['arms'].items():
    for key, expected in saved['metrics'].items():
        mode, role = key.split('/')
        subset = [p for p in predictions if p['arm'] == arm and p['mode'] == mode and
                  p['role'] == role and p['label'] in {'useful', 'irrelevant'} and
                  not by_id[p['row_id']].get('defect', False)]
        assert len({p['row_id'] for p in subset}) == len(subset) == expected['n']
        y = np.array([p['label'] == 'useful' for p in subset], dtype=int)
        probs = np.array([p['probability'] for p in subset])
        assert np.isfinite(probs).all() and ((0 <= probs) & (probs <= 1)).all()
        predicted = probs >= .5
        tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
        metrics = {'accuracy': accuracy_score(y, predicted),
                   'balanced_accuracy': balanced_accuracy_score(y, predicted),
                   'f1': f1_score(y, predicted, zero_division=0),
                   'brier': brier_score_loss(y, probs), 'roc_auc': roc_auc_score(y, probs),
                   'nll': float(-np.log(np.maximum(np.where(y, probs, 1-probs), 1e-7)).mean()),
                   'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)}
        for name, value in metrics.items():
            delta = abs(value - expected[name])
            max_delta = max(max_delta, delta)
            assert delta < 1e-9, (arm, key, name, value, expected[name])
        checks.append({'arm': arm, 'metric_group': key, 'n': len(subset)})
result = {'status': 'passed', 'sklearn': sklearn.__version__, 'numpy': np.__version__,
          'checks': checks, 'max_metric_delta': max_delta, 'family_disjoint': True,
          'test_used': False, 'prediction_records': len(predictions),
          'predictions_sha256': hashlib.sha256((base/'heads-v1/predictions.jsonl').read_bytes()).hexdigest()}
with (report/'numerical-verification.json').open('x') as f:
    json.dump(result, f, indent=2)
print(json.dumps(result))
