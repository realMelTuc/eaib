"""
EAIB test configuration and fixtures.
Uses an in-memory mock DB so tests run without a live Supabase connection.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── In-memory intel store ─────────────────────────────────────────────────────

INTEL_REPORTS = {
    1: {
        'id': 1, 'title': 'Hostile Fleet in Jita', 'system_name': 'Jita',
        'region_name': 'The Forge', 'reporter_name': 'TestPilot',
        'character_name': 'Evil Dude', 'corporation_name': 'Bad Corp',
        'alliance_name': 'Bad Alliance', 'threat_level': 'high',
        'category': 'fleet', 'status': 'active', 'description': 'Large hostile fleet',
        'raw_text': 'Evil Dude > Jita 10 man fleet', 'ship_type': 'Battleship',
        'pilot_count': 10, 'created_at': None, 'updated_at': None, 'expires_at': None,
    },
    2: {
        'id': 2, 'title': 'Gate Camp Amarr', 'system_name': 'Amarr',
        'region_name': 'Domain', 'reporter_name': 'Scout1',
        'character_name': None, 'corporation_name': None,
        'alliance_name': None, 'threat_level': 'critical',
        'category': 'camp', 'status': 'active', 'description': 'Gate camp at Amarr',
        'raw_text': None, 'ship_type': 'Sabre', 'pilot_count': 5,
        'created_at': None, 'updated_at': None, 'expires_at': None,
    },
    3: {
        'id': 3, 'title': 'Resolved Threat', 'system_name': 'Dodixie',
        'region_name': 'Sinq Laison', 'reporter_name': 'Scout2',
        'character_name': None, 'corporation_name': None,
        'alliance_name': None, 'threat_level': 'medium',
        'category': 'other', 'status': 'resolved', 'description': None,
        'raw_text': None, 'ship_type': None, 'pilot_count': None,
        'created_at': None, 'updated_at': None, 'expires_at': None,
    },
}

TAGS = {
    1: {'id': 1, 'name': 'Hostile Fleet', 'color': '#ef4444', 'description': 'Active hostile fleet'},
    2: {'id': 2, 'name': 'Gate Camp',     'color': '#f0a020', 'description': 'Gate camp in progress'},
    3: {'id': 3, 'name': 'Capital Ship',  'color': '#a855f7', 'description': 'Capital or super-capital'},
}

REPORT_TAGS = {
    1: [1],  # report 1 -> Hostile Fleet
    2: [2],  # report 2 -> Gate Camp
}

COMMENTS = {
    1: [
        {'id': 1, 'report_id': 1, 'author_name': 'Pilot A', 'body': 'Confirmed still active', 'created_at': None},
    ],
    2: [],
}


def make_mock_conn():
    """Build a mock DB connection serving in-memory EAIB data."""

    class MockCursor:
        def __init__(self):
            self._results = []
            self._rowcount = 0

        def execute(self, query, params=None):
            q = query.strip().lower()
            self._results = []
            self._rowcount = 0

            # ── GROUP BY queries — most specific first ────────────────────

            if 'group by threat_level' in q:
                from collections import Counter
                active = [r['threat_level'] for r in INTEL_REPORTS.values() if r['status'] == 'active']
                counts = Counter(active)
                self._results = [{'threat_level': k, 'cnt': v} for k, v in counts.items()]

            elif 'group by category' in q:
                from collections import Counter
                active_cats = [r['category'] for r in INTEL_REPORTS.values() if r['status'] == 'active']
                counts = Counter(active_cats)
                self._results = [{'category': k, 'cnt': v} for k, v in counts.items()]

            elif 'group by system_name' in q or ('system_name' in q and 'group by' in q and 'region_name' in q):
                self._results = [
                    {'system_name': 'Jita', 'region_name': 'The Forge', 'report_count': 1, 'max_threat_num': 3, 'top_threat': 'high'},
                    {'system_name': 'Amarr', 'region_name': 'Domain', 'report_count': 1, 'max_threat_num': 4, 'top_threat': 'critical'},
                ]

            elif 'group by region_name' in q:
                self._results = [
                    {'region_name': 'The Forge', 'cnt': 1, 'critical_cnt': 0},
                    {'region_name': 'Domain', 'cnt': 1, 'critical_cnt': 1},
                ]

            # ── Tags queries — specific before generic ────────────────────

            elif 'eaib_tags' in q and 'left join' in q and 'group by' in q and 'count' in q:
                self._results = [
                    {**t, 'report_count': sum(1 for ids in REPORT_TAGS.values() if t['id'] in ids)}
                    for t in TAGS.values()
                ]

            elif 'eaib_tags' in q and 'eaib_report_tags' in q and 'where rt.report_id' in q:
                rid = params[0] if params else None
                tag_ids = REPORT_TAGS.get(rid, [])
                self._results = [TAGS[tid] for tid in tag_ids if tid in TAGS]

            elif 'select *' in q and 'eaib_tags' in q:
                self._results = list(TAGS.values())

            elif 'select id, name, color' in q and 'eaib_tags' in q:
                self._results = [{'id': t['id'], 'name': t['name'], 'color': t['color']} for t in TAGS.values()]

            elif 'select t.id' in q and 'eaib_tags' in q and 'eaib_report_tags' in q:
                rid = params[0] if params else None
                tag_ids = REPORT_TAGS.get(rid, [])
                self._results = [TAGS[tid] for tid in tag_ids if tid in TAGS]

            elif 'insert into eaib_tags' in q:
                new_id = max(TAGS.keys()) + 1 if TAGS else 1
                self._results = [{'id': new_id}]
                self._rowcount = 1

            elif 'delete from eaib_tags' in q:
                self._rowcount = 1

            # ── Intel reports queries ──────────────────────────────────────

            elif 'eaib_intel_reports' in q and 'where id =' in q:
                rid = params[0] if params else None
                r = INTEL_REPORTS.get(rid)
                self._results = [r] if r else []

            elif 'count(*)' in q and 'eaib_intel_reports' in q:
                rows = list(INTEL_REPORTS.values())
                if params:
                    for p in (params if isinstance(params, (list, tuple)) else [params]):
                        if p in ('active', 'resolved', 'expired', 'false_positive'):
                            rows = [r for r in rows if r['status'] == p]
                        elif p in ('high', 'medium', 'low', 'critical'):
                            rows = [r for r in rows if r['threat_level'] == p]
                # Handle hardcoded conditions in the query itself
                if "status='active'" in q or "status = 'active'" in q:
                    rows2 = [r for r in INTEL_REPORTS.values() if r['status'] == 'active']
                    if "threat_level='critical'" in q or "threat_level = 'critical'" in q:
                        rows2 = [r for r in rows2 if r['threat_level'] == 'critical']
                    self._results = [{'cnt': len(rows2)}]
                elif "status='resolved'" in q or "status = 'resolved'" in q:
                    rows2 = [r for r in INTEL_REPORTS.values() if r['status'] == 'resolved']
                    self._results = [{'cnt': len(rows2)}]
                else:
                    self._results = [{'cnt': len(rows)}]

            elif 'from eaib_intel_reports' in q and 'order by' in q:
                rows = list(INTEL_REPORTS.values())
                if params:
                    for p in (params if isinstance(params, (list, tuple)) else [params]):
                        if p in ('active', 'resolved', 'expired', 'false_positive'):
                            rows = [r for r in rows if r['status'] == p]
                        elif p in ('high', 'medium', 'low', 'critical'):
                            rows = [r for r in rows if r['threat_level'] == p]
                self._results = rows

            elif 'insert into eaib_intel_reports' in q:
                new_id = max(INTEL_REPORTS.keys()) + 1 if INTEL_REPORTS else 1
                self._results = [{'id': new_id}]
                self._rowcount = 1

            elif 'update eaib_intel_reports' in q:
                self._rowcount = 1

            # ── Comments queries ───────────────────────────────────────────

            elif 'from eaib_comments' in q and 'where report_id' in q:
                rid = params[0] if params else None
                self._results = COMMENTS.get(rid, [])

            elif 'insert into eaib_comments' in q:
                new_id = 100
                self._results = [{'id': new_id}]
                self._rowcount = 1

            # ── Report tags ─────────────────────────────────────────────────

            elif 'insert into eaib_report_tags' in q:
                self._rowcount = 1

            elif 'delete from eaib_report_tags' in q:
                self._rowcount = 1

            # ── Health check ────────────────────────────────────────────────

            elif 'select 1' in q:
                self._results = [{'ok': 1}]

            # ── Search ──────────────────────────────────────────────────────

            elif 'ilike' in q and 'eaib_intel_reports' in q:
                term = params[0].replace('%', '').lower() if params else ''
                self._results = [
                    r for r in INTEL_REPORTS.values()
                    if term in (r.get('title') or '').lower()
                    or term in (r.get('system_name') or '').lower()
                ][:10]

        def fetchone(self):
            return self._results[0] if self._results else None

        def fetchall(self):
            return list(self._results)

        @property
        def rowcount(self):
            return self._rowcount

        def close(self):
            pass

    class MockConn:
        def cursor(self): return MockCursor()
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    return MockConn()


@pytest.fixture
def mock_conn():
    return make_mock_conn()


@pytest.fixture
def app():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'app_module',
        os.path.join(os.path.dirname(__file__), '..', 'app.py')
    )
    module = importlib.util.module_from_spec(spec)
    # Patch db before loading
    with patch.dict('os.environ', {
        'FLASK_SECRET_KEY': 'test-key',
        'SUPABASE_DB_HOST': 'localhost',
        'SUPABASE_DB_NAME': 'postgres',
        'SUPABASE_DB_USER': 'postgres',
        'SUPABASE_DB_PASSWORD': 'test',
        'SUPABASE_DB_PORT': '6543',
    }):
        with patch('db.pg8000'):
            try:
                spec.loader.exec_module(module)
            except Exception:
                pass
    return module.app if hasattr(module, 'app') else None


@pytest.fixture
def client(app):
    if app is None:
        pytest.skip('App could not be loaded')
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c
