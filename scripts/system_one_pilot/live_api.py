"""OpenRouter transport with durable reservations; no automatic paid retries."""
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import json
import math
import os
from pathlib import Path
import sqlite3
import ssl
import urllib.request
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

from .data import digest

ROOT = Path(__file__).resolve().parents[2]
DEEPSEEK = 'deepseek/deepseek-v4.1-flash-1017'
QWEN = 'qwen/qwen3.8-27b'
LIMITS = {'collection': 1_000_000_000, 'annotation': 500_000_000}
PROFILES = {
    DEEPSEEK: {'endpoint': 'deepinfra/fp8', 'provider': 'DeepInfra', 'input': '.30', 'output': '1.20'},
    QWEN: {'endpoint': 'deepinfra/bf16', 'provider': 'DeepInfra', 'input': '.20', 'output': '2.50'},
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


@contextmanager
def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS api_calls (
        series TEXT NOT NULL, call_id TEXT NOT NULL, request_hash TEXT NOT NULL,
        request TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL,
        input_bound INTEGER NOT NULL, reserved_nusd INTEGER NOT NULL,
        actual_nusd INTEGER, response TEXT, error TEXT, finished_at TEXT,
        PRIMARY KEY(series,call_id));
      CREATE TRIGGER IF NOT EXISTS protect_paid_response BEFORE UPDATE ON api_calls
        WHEN OLD.response IS NOT NULL BEGIN SELECT RAISE(ABORT,'immutable API response'); END;
      CREATE TRIGGER IF NOT EXISTS protect_paid_delete BEFORE DELETE ON api_calls
        BEGIN SELECT RAISE(ABORT,'immutable API history'); END;
      CREATE TABLE IF NOT EXISTS api_receipts (
        series TEXT NOT NULL, call_id TEXT NOT NULL, kind TEXT NOT NULL,
        body TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY(series,call_id,kind));
      CREATE TRIGGER IF NOT EXISTS protect_receipt_update BEFORE UPDATE ON api_receipts
        BEGIN SELECT RAISE(ABORT,'immutable request receipt'); END;
      CREATE TRIGGER IF NOT EXISTS protect_receipt_delete BEFORE DELETE ON api_receipts
        BEGIN SELECT RAISE(ABORT,'immutable request receipt'); END;
      CREATE TABLE IF NOT EXISTS api_reconciliations (
        series TEXT NOT NULL, call_id TEXT NOT NULL, method TEXT NOT NULL,
        evidence TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY(series,call_id));
      CREATE TRIGGER IF NOT EXISTS protect_reconciliation_update BEFORE UPDATE ON api_reconciliations
        BEGIN SELECT RAISE(ABORT,'immutable reconciliation'); END;
      CREATE TRIGGER IF NOT EXISTS protect_reconciliation_delete BEFORE DELETE ON api_reconciliations
        BEGIN SELECT RAISE(ABORT,'immutable reconciliation'); END;
      CREATE TABLE IF NOT EXISTS api_daily_policy (
        id INTEGER PRIMARY KEY CHECK(id=1), limit_nusd INTEGER NOT NULL, timezone_name TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS api_series_limits (series TEXT PRIMARY KEY, limit_nusd INTEGER NOT NULL);
      CREATE TRIGGER IF NOT EXISTS protect_daily_update BEFORE UPDATE ON api_daily_policy
        BEGIN SELECT RAISE(ABORT,'immutable daily policy'); END;
      CREATE TRIGGER IF NOT EXISTS protect_daily_delete BEFORE DELETE ON api_daily_policy
        BEGIN SELECT RAISE(ABORT,'immutable daily policy'); END;
      CREATE TRIGGER IF NOT EXISTS protect_series_update BEFORE UPDATE ON api_series_limits
        BEGIN SELECT RAISE(ABORT,'immutable series authorization'); END;
      CREATE TRIGGER IF NOT EXISTS protect_series_delete BEFORE DELETE ON api_series_limits
        BEGIN SELECT RAISE(ABORT,'immutable series authorization'); END;
    ''')
    try:
        with db:
            yield db
    finally:
        db.close()


class BudgetError(RuntimeError):
    pass


def configure_daily_budget(path,limit_nusd,timezone_name):
    if type(limit_nusd) is not int or limit_nusd<=0:raise ValueError('invalid daily limit')
    ZoneInfo(timezone_name)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT limit_nusd,timezone_name FROM api_daily_policy WHERE id=1').fetchone()
        if old and tuple(old)!=(limit_nusd,timezone_name):raise ValueError('daily policy differs')
        if not old:db.execute('INSERT INTO api_daily_policy VALUES(1,?,?)',(limit_nusd,timezone_name))


def authorize_series(path,series,limit_nusd):
    if not isinstance(series,str) or not series or series in LIMITS or type(limit_nusd) is not int or limit_nusd<=0:
        raise ValueError('invalid new series authorization')
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM api_daily_policy').fetchone():raise ValueError('new series requires daily policy')
        old=db.execute('SELECT limit_nusd FROM api_series_limits WHERE series=?',(series,)).fetchone()
        if old and old[0]!=limit_nusd:raise ValueError('series authorization differs')
        if not old:db.execute('INSERT INTO api_series_limits VALUES(?,?)',(series,limit_nusd))


def _daily(db,now):
    policy=db.execute('SELECT * FROM api_daily_policy WHERE id=1').fetchone()
    if not policy:return None
    zone=ZoneInfo(policy['timezone_name'])
    day=datetime.fromisoformat(now).astimezone(zone).date().isoformat()
    rows=[r for r in db.execute('SELECT created_at,actual_nusd,reserved_nusd FROM api_calls')
          if datetime.fromisoformat(r['created_at']).astimezone(zone).date().isoformat()==day]
    held=sum(r['actual_nusd'] if r['actual_nusd'] is not None else r['reserved_nusd'] for r in rows)
    return {'date':day,'timezone':policy['timezone_name'],'calls':len(rows),
            'limit_usd':policy['limit_nusd']/1e9,'charged_or_held_usd':held/1e9,
            'remaining_usd':max(0,policy['limit_nusd']-held)/1e9,
            'held_nusd':held,'limit_nusd':policy['limit_nusd']}


def daily_summary(path,now=None):
    with connect(path) as db:return _daily(db,now or utc())


def key():
    value = os.environ.get('OPENROUTER_API_KEY')
    if not value:
        for line in (ROOT / '.env').read_text().splitlines():
            if line.startswith('OPENROUTER_API_KEY='):
                value = line.split('=', 1)[1].strip().strip('\"\'')
    if not value:
        raise RuntimeError('OPENROUTER_API_KEY missing')
    return value


def http_json(route, payload=None, on_generation=None):
    import certifi
    request = urllib.request.Request('https://openrouter.ai/api/v1/' + route,
        data=dumps(payload).encode() if payload is not None else None,
        headers={'Authorization': 'Bearer ' + key(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=180,
            context=ssl.create_default_context(cafile=certifi.where())) as response:
        generation_id=response.headers.get('X-Generation-Id')
        if on_generation and generation_id:on_generation(generation_id)
        return json.load(response)


def preflight(folder):
    """Archive live endpoint facts; fail closed if price/support cannot be bounded."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    facts = {'at': utc(), 'key': {k:v for k,v in http_json('key')['data'].items()
                if k in {'limit','limit_remaining','usage','is_free_tier'}}}
    for model, profile in PROFILES.items():
        data = http_json('models/' + model + '/endpoints')['data']
        matches = [e for e in data['endpoints'] if e['tag'] == profile['endpoint']]
        if len(matches) != 1:
            raise BudgetError('Selected endpoint unavailable: ' + model)
        endpoint = matches[0]
        required = {'max_tokens', 'reasoning', 'response_format', 'structured_outputs', 'tools'}
        if endpoint.get('status') != 0 or not required <= set(endpoint['supported_parameters']):
            raise BudgetError('Selected endpoint lacks required parameters: ' + model)
        pricing = endpoint['pricing']
        discount = Decimal(str(pricing.get('discount', 0)))
        if not 0 <= discount < 1:
            raise BudgetError('Unbounded endpoint discount')
        for name, cap in [('prompt', 'input'), ('completion', 'output')]:
            values = [Decimal(str(pricing[name])) / (1-discount)]
            values += [Decimal(str(o[name])) for o in pricing.get('overrides', []) if name in o]
            if any(not x.is_finite() or x < 0 for x in values) or max(values)*1_000_000 > Decimal(profile[cap]):
                raise BudgetError('Endpoint tariff exceeds fixed reservation cap: ' + model)
        facts[model] = data
    target = folder / ('preflight-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    target.write_text(json.dumps(facts, ensure_ascii=False, indent=2))
    return facts


class PaidClient:
    def __init__(self, db, series, transport=None):
        self.path, self.series = Path(db), series
        self.transport = transport
        with connect(self.path) as conn:
            row=conn.execute('SELECT limit_nusd FROM api_series_limits WHERE series=?',(series,)).fetchone()
        self.limit_nusd=LIMITS.get(series,row[0] if row else None)
        if self.limit_nusd is None:raise ValueError('unknown series')

    def summary(self):
        with connect(self.path) as db:
            rows = db.execute('SELECT * FROM api_calls WHERE series=?', (self.series,)).fetchall()
            accounted={r[0] for r in db.execute('SELECT call_id FROM api_reconciliations WHERE series=?',(self.series,))}
        return {'series': self.series, 'limit_usd': self.limit_nusd/1e9,
                'calls': len(rows), 'actual_usd': sum(r['actual_nusd'] or 0 for r in rows)/1e9,
                'charged_or_held_usd': sum(r['actual_nusd'] if r['actual_nusd'] is not None
                                          else r['reserved_nusd'] for r in rows)/1e9,
                'unresolved': sum(r['status'] != 'complete' and r['call_id'] not in accounted for r in rows),
                'conservatively_accounted_calls':len(accounted)}

    def account_rejected_bound(self, call_id, evidence):
        """Explicit investigation receipt: retain the ENTIRE maximum, never infer zero cost."""
        if not isinstance(evidence,dict) or not evidence.get('reason'):
            raise ValueError('investigation evidence required')
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM api_calls WHERE series=? AND call_id=?',(self.series,call_id)).fetchone()
            error=json.loads(row['error'] or '{}') if row else {}
            definite=error.get('http_status') in {400,401,402,403,404,422}
            if row and error.get('http_status')==429:
                # Manual investigation only: a specific pre-inference upstream rejection.
                # Generic 429, mid-generation failures and timeouts remain unresolved.
                try:
                    stored=json.loads(row['response']);body=json.loads(stored['body']);meta=body['error']['metadata']
                    definite=(stored['http_status']==429 and body['error']['code']==429
                        and body['error']['message']=='Provider returned error'
                        and meta.get('provider_name')=='DeepInfra' and meta.get('provider_error_code')=='engine_overloaded'
                        and meta.get('limit_source')=='upstream_provider_shared_pool'
                        and not body.get('choices') and not body.get('id')
                        and evidence.get('response_sha256')==digest(stored))
                except (TypeError,KeyError,json.JSONDecodeError):definite=False
            if not row or row['status']!='unknown' or not definite:
                raise BudgetError('only definite HTTP request rejection may be conservatively accounted')
            db.execute('INSERT INTO api_reconciliations VALUES(?,?,?,?,?)',
                       (self.series,call_id,'full_reserved_upper_bound',dumps(evidence),utc()))

    def complete(self, call_id, payload):
        request = copy.deepcopy(payload)
        profile = PROFILES[request['model']]
        maximum = request.get('max_tokens')
        if type(maximum) is not int or not 1 <= maximum <= 2048:
            raise ValueError('explicit max_tokens in 1..2048 required')
        request['provider'] = {'only': [profile['endpoint']], 'allow_fallbacks': False,
            'require_parameters': True, 'max_price': {'prompt': float(profile['input']),
                                                     'completion': float(profile['output'])}}
        # Every UTF-8 byte can cost at most one text token; ample chat/tool framing.
        bound = len(dumps(request).encode()) + 4096 + 256 * (len(request['messages']) + len(request.get('tools') or []))
        reserve = int(((Decimal(bound)*Decimal(profile['input']) +
                       Decimal(maximum)*Decimal(profile['output'])) * 1000).to_integral_value(rounding=ROUND_CEILING))
        request_hash = digest(request)
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM api_calls WHERE series=? AND call_id=?', (self.series, call_id)).fetchone()
            if old:
                if old['request_hash'] != request_hash:
                    raise ValueError('request changed for durable call ID')
                if old['status'] == 'complete':
                    return json.loads(old['response'])
                raise BudgetError('unknown/unresolved prior outcome; reconcile before retry')
            now=utc();daily=_daily(db,now)
            if daily:
                unresolved=db.execute("SELECT 1 FROM api_calls c LEFT JOIN api_reconciliations r ON c.series=r.series AND c.call_id=r.call_id WHERE c.status!='complete' AND r.call_id IS NULL LIMIT 1").fetchone()
                if unresolved:raise BudgetError('unknown/unresolved outcome blocks all daily roles')
                if daily['held_nusd']+reserve>daily['limit_nusd']:
                    raise BudgetError('shared daily budget exhausted before HTTP')
            rows = db.execute('SELECT * FROM api_calls WHERE series=?', (self.series,)).fetchall()
            accounted={r[0] for r in db.execute('SELECT call_id FROM api_reconciliations WHERE series=?',(self.series,))}
            if any(r['status'] != 'complete' and r['call_id'] not in accounted for r in rows):
                raise BudgetError('unknown/unresolved outcome blocks series')
            spent = sum(r['actual_nusd'] if r['actual_nusd'] is not None else r['reserved_nusd'] for r in rows)
            if spent + reserve > self.limit_nusd:
                raise BudgetError('persistent series budget exhausted before HTTP')
            db.execute('INSERT INTO api_calls(series,call_id,request_hash,request,created_at,status,input_bound,reserved_nusd) VALUES(?,?,?,?,?,?,?,?)',
                       (self.series, call_id, request_hash, dumps(request), now, 'reserved', bound, reserve))
        def record_generation(generation_id):
            with connect(self.path) as db:
                db.execute('INSERT INTO api_receipts VALUES(?,?,?,?,?)',
                    (self.series,call_id,'response_headers',dumps({'generation_id':generation_id}),utc()))
        try:
            response = self.transport(request) if self.transport else http_json('chat/completions',request,on_generation=record_generation)
            # Persist even an API error response; it is evidence, never an uncertain label.
            cost = response.get('usage', {}).get('cost')
            actual = None
            if isinstance(cost, (float, int)) and not isinstance(cost, bool) and math.isfinite(cost) and cost >= 0:
                actual = int((Decimal(str(cost))*1_000_000_000).to_integral_value(rounding=ROUND_CEILING))
            status = 'complete' if actual is not None and actual <= reserve and response.get('choices') else 'unreconciled'
            with connect(self.path) as db:
                db.execute('UPDATE api_calls SET status=?,actual_nusd=?,response=?,finished_at=? WHERE series=? AND call_id=?',
                    (status, actual, dumps(response), utc(), self.series, call_id))
            if status != 'complete' and not response.get('choices'):
                raise BudgetError('API response incomplete; series stopped')
            return response
        except Exception as exc:
            # Exception messages may contain HTTP headers; retain type/status only.
            raw_error=None
            if isinstance(exc,HTTPError):
                try:
                    body=exc.read().decode('utf-8','replace')
                    try:body=body.replace(key(),'[REDACTED]')
                    except (OSError,RuntimeError):pass
                    raw_error=dumps({'http_status':exc.code,'body':body})
                except Exception as body_error:
                    raw_error=dumps({'http_status':exc.code,'body_unavailable':type(body_error).__name__})
            with connect(self.path) as db:
                db.execute("UPDATE api_calls SET status='unknown',error=?,finished_at=?,response=? WHERE series=? AND call_id=? AND response IS NULL",
                    (dumps({'type': type(exc).__name__, 'http_status': getattr(exc, 'code', None)}), utc(),raw_error, self.series, call_id))
            raise BudgetError('unknown request outcome retained; no automatic retry') from None
