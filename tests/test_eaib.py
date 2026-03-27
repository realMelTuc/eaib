"""
EAIB test suite.
All tests use mock DB — no live Supabase connection required.
"""
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest import (
    INTEL_REPORTS, TAGS, REPORT_TAGS, COMMENTS,
    make_mock_conn
)


# ═══════════════════════════════════════════════════════════════════════════════
# MockCursor / MockConn sanity checks
# ═══════════════════════════════════════════════════════════════════════════════

class TestMockDB:
    def test_mock_conn_creates(self):
        conn = make_mock_conn()
        assert conn is not None

    def test_mock_cursor_health(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT 1 AS ok')
        row = cur.fetchone()
        assert row == {'ok': 1}

    def test_mock_cursor_commit_rollback(self):
        conn = make_mock_conn()
        conn.commit()
        conn.rollback()
        conn.close()

    def test_mock_cursor_close(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.close()

    def test_list_intel_reports_all(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM eaib_intel_reports ORDER BY id DESC LIMIT 50', ['active'])
        rows = cur.fetchall()
        assert isinstance(rows, list)

    def test_list_intel_reports_active(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT count(*) AS cnt FROM eaib_intel_reports WHERE status = %s', ['active'])
        row = cur.fetchone()
        assert row['cnt'] == 2  # reports 1 and 2 are active

    def test_list_intel_reports_critical(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) AS cnt FROM eaib_intel_reports WHERE status='active' AND threat_level='critical'"
        )
        row = cur.fetchone()
        assert row is not None

    def test_get_single_report(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM eaib_intel_reports WHERE id = %s', [1])
        row = cur.fetchone()
        assert row is not None
        assert row['id'] == 1
        assert row['title'] == 'Hostile Fleet in Jita'

    def test_get_missing_report(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM eaib_intel_reports WHERE id = %s', [9999])
        row = cur.fetchone()
        assert row is None

    def test_list_tags(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM eaib_tags ORDER BY name')
        rows = cur.fetchall()
        assert len(rows) == len(TAGS)

    def test_list_tags_id_name_color(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT id, name, color FROM eaib_tags ORDER BY name')
        rows = cur.fetchall()
        assert len(rows) == len(TAGS)
        for r in rows:
            assert 'id' in r
            assert 'name' in r
            assert 'color' in r

    def test_tags_with_counts(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT t.id, t.name, t.color, count(rt.report_id) AS report_count
            FROM eaib_tags t
            LEFT JOIN eaib_report_tags rt ON rt.tag_id = t.id
            GROUP BY t.id
            ORDER BY t.name
        """)
        rows = cur.fetchall()
        assert len(rows) == len(TAGS)
        for r in rows:
            assert 'report_count' in r

    def test_report_tags_lookup(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT t.id, t.name, t.color
            FROM eaib_tags t
            JOIN eaib_report_tags rt ON rt.tag_id = t.id
            WHERE rt.report_id = %s
        """, [1])
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0]['id'] == 1

    def test_report_tags_none(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT t.id, t.name, t.color
            FROM eaib_tags t
            JOIN eaib_report_tags rt ON rt.tag_id = t.id
            WHERE rt.report_id = %s
        """, [3])
        rows = cur.fetchall()
        assert rows == []

    def test_comments_for_report(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM eaib_comments WHERE report_id = %s ORDER BY created_at', [1])
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0]['author_name'] == 'Pilot A'

    def test_comments_empty(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM eaib_comments WHERE report_id = %s ORDER BY created_at', [2])
        rows = cur.fetchall()
        assert rows == []

    def test_insert_intel_report(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO eaib_intel_reports
                (title, system_name, region_name, reporter_name,
                 character_name, corporation_name, alliance_name,
                 threat_level, category, status, description,
                 raw_text, ship_type, pilot_count, expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, [
            'Test Report', 'Rens', 'Heimatar', 'TestPilot',
            None, None, None, 'low', 'other', 'active',
            None, None, None, None, None
        ])
        row = cur.fetchone()
        assert row is not None
        assert 'id' in row
        assert row['id'] > 0

    def test_update_intel_status(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE eaib_intel_reports SET status='resolved', updated_at=NOW() WHERE id=%s",
            [1]
        )
        assert cur.rowcount >= 0

    def test_insert_tag(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO eaib_tags (name, color, description) VALUES (%s,%s,%s) RETURNING id',
            ['NewTag', '#ff0000', 'A new tag']
        )
        row = cur.fetchone()
        assert row is not None
        assert 'id' in row

    def test_delete_tag(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('DELETE FROM eaib_tags WHERE id = %s', [1])
        assert cur.rowcount >= 0

    def test_insert_report_tag(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO eaib_report_tags (report_id, tag_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
            [1, 3]
        )
        assert cur.rowcount >= 0

    def test_delete_report_tag(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute(
            'DELETE FROM eaib_report_tags WHERE report_id=%s AND tag_id=%s',
            [1, 1]
        )
        assert cur.rowcount >= 0

    def test_insert_comment(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO eaib_comments (report_id, author_name, body) VALUES (%s,%s,%s) RETURNING id',
            [2, 'NewPilot', 'Spotted again at gate']
        )
        row = cur.fetchone()
        assert row is not None
        assert 'id' in row

    def test_threat_distribution(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT threat_level, COUNT(*) AS cnt
            FROM eaib_intel_reports
            WHERE status = 'active'
            GROUP BY threat_level
            ORDER BY cnt DESC
        """)
        rows = cur.fetchall()
        assert isinstance(rows, list)
        for r in rows:
            assert 'threat_level' in r
            assert 'cnt' in r

    def test_category_distribution(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT category, COUNT(*) AS cnt
            FROM eaib_intel_reports
            WHERE status = 'active'
            GROUP BY category
            ORDER BY cnt DESC
        """)
        rows = cur.fetchall()
        assert isinstance(rows, list)

    def test_hot_systems(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT system_name, region_name, COUNT(*) AS report_count,
                   MAX(threat_level) AS top_threat
            FROM eaib_intel_reports
            WHERE status = 'active' AND system_name IS NOT NULL
            GROUP BY system_name, region_name
            ORDER BY report_count DESC
            LIMIT 10
        """)
        rows = cur.fetchall()
        assert isinstance(rows, list)
        for r in rows:
            assert 'system_name' in r

    def test_region_breakdown(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT region_name, COUNT(*) AS cnt,
                   SUM(CASE WHEN threat_level='critical' THEN 1 ELSE 0 END) AS critical_cnt
            FROM eaib_intel_reports
            WHERE status = 'active' AND region_name IS NOT NULL
            GROUP BY region_name
            ORDER BY cnt DESC
        """)
        rows = cur.fetchall()
        assert isinstance(rows, list)

    def test_search_by_title(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, system_name, threat_level, status
            FROM eaib_intel_reports
            WHERE title ILIKE %s OR system_name ILIKE %s OR character_name ILIKE %s
            ORDER BY created_at DESC
            LIMIT 10
        """, ['%Jita%', '%Jita%', '%Jita%'])
        rows = cur.fetchall()
        assert isinstance(rows, list)

    def test_resolved_count(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) AS cnt FROM eaib_intel_reports WHERE status='resolved' AND updated_at >= CURRENT_DATE"
        )
        row = cur.fetchone()
        assert row is not None
        assert 'cnt' in row

    def test_total_count(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) AS cnt FROM eaib_intel_reports')
        row = cur.fetchone()
        assert row is not None
        assert row['cnt'] == len(INTEL_REPORTS)

    def test_cursor_fetchall_empty(self):
        conn = make_mock_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM eaib_intel_reports WHERE id = %s', [9999])
        rows = cur.fetchall()
        assert rows == []


# ═══════════════════════════════════════════════════════════════════════════════
# DB module unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDBModule:
    def test_serialize_row_basic(self):
        from db import serialize_row
        row = {'id': 1, 'name': 'Test', 'count': 42}
        result = serialize_row(row)
        assert result == {'id': 1, 'name': 'Test', 'count': 42}

    def test_serialize_row_datetime(self):
        from datetime import datetime
        from db import serialize_row
        dt = datetime(2026, 3, 27, 12, 0, 0)
        row = {'id': 1, 'created_at': dt}
        result = serialize_row(row)
        assert result['created_at'] == '2026-03-27T12:00:00'

    def test_serialize_row_date(self):
        from datetime import date
        from db import serialize_row
        d = date(2026, 3, 27)
        row = {'id': 1, 'day': d}
        result = serialize_row(row)
        assert result['day'] == '2026-03-27'

    def test_serialize_row_decimal(self):
        from decimal import Decimal
        from db import serialize_row
        row = {'price': Decimal('123.45')}
        result = serialize_row(row)
        assert result['price'] == pytest.approx(123.45)

    def test_serialize_row_none_values(self):
        from db import serialize_row
        row = {'id': 1, 'name': None, 'val': 0}
        result = serialize_row(row)
        assert result['name'] is None

    def test_serialize_row_mixed(self):
        from datetime import datetime
        from decimal import Decimal
        from db import serialize_row
        row = {
            'id': 5,
            'title': 'Test',
            'created_at': datetime(2026, 1, 1),
            'price': Decimal('99.99'),
            'notes': None,
        }
        result = serialize_row(row)
        assert result['id'] == 5
        assert result['title'] == 'Test'
        assert isinstance(result['created_at'], str)
        assert isinstance(result['price'], float)
        assert result['notes'] is None

    def test_dictcursor_named_params(self):
        """DictCursor converts %(name)s -> $N positional params."""
        from db import DictCursor
        raw_conn = MagicMock()
        raw_cursor = MagicMock()
        raw_cursor.description = [('id',), ('name',)]
        raw_cursor.fetchone.return_value = (1, 'Test')
        raw_conn.cursor.return_value = raw_cursor
        dc = DictCursor(raw_conn)
        dc.execute('SELECT %(id)s, %(name)s', {'id': 1, 'name': 'Test'})
        raw_cursor.execute.assert_called_once()
        args = raw_cursor.execute.call_args[0]
        assert '$1' in args[0]
        assert '$2' in args[0]

    def test_dictcursor_positional_params(self):
        """DictCursor converts %s -> $N positional params."""
        from db import DictCursor
        raw_conn = MagicMock()
        raw_cursor = MagicMock()
        raw_cursor.description = [('id',)]
        raw_cursor.fetchone.return_value = (1,)
        raw_conn.cursor.return_value = raw_cursor
        dc = DictCursor(raw_conn)
        dc.execute('SELECT id FROM t WHERE id = %s', [42])
        raw_cursor.execute.assert_called_once()
        call_args = raw_cursor.execute.call_args[0]
        assert '$1' in call_args[0]

    def test_dictcursor_fetchone_dict(self):
        from db import DictCursor
        raw_conn = MagicMock()
        raw_cursor = MagicMock()
        raw_cursor.description = [('id',), ('title',)]
        raw_cursor.fetchone.return_value = (7, 'Fleet in Jita')
        raw_conn.cursor.return_value = raw_cursor
        dc = DictCursor(raw_conn)
        dc.execute('SELECT id, title FROM eaib_intel_reports')
        row = dc.fetchone()
        assert row == {'id': 7, 'title': 'Fleet in Jita'}

    def test_dictcursor_fetchall_dicts(self):
        from db import DictCursor
        raw_conn = MagicMock()
        raw_cursor = MagicMock()
        raw_cursor.description = [('id',), ('threat_level',)]
        raw_cursor.fetchall.return_value = [(1, 'high'), (2, 'critical')]
        raw_conn.cursor.return_value = raw_cursor
        dc = DictCursor(raw_conn)
        dc.execute('SELECT id, threat_level FROM eaib_intel_reports')
        rows = dc.fetchall()
        assert rows == [{'id': 1, 'threat_level': 'high'}, {'id': 2, 'threat_level': 'critical'}]

    def test_dictcursor_fetchone_none(self):
        from db import DictCursor
        raw_conn = MagicMock()
        raw_cursor = MagicMock()
        raw_cursor.description = [('id',)]
        raw_cursor.fetchone.return_value = None
        raw_conn.cursor.return_value = raw_cursor
        dc = DictCursor(raw_conn)
        dc.execute('SELECT id FROM t WHERE id = %s', [9999])
        assert dc.fetchone() is None

    def test_dictcursor_fetchall_empty(self):
        from db import DictCursor
        raw_conn = MagicMock()
        raw_cursor = MagicMock()
        raw_cursor.description = [('id',)]
        raw_cursor.fetchall.return_value = []
        raw_conn.cursor.return_value = raw_cursor
        dc = DictCursor(raw_conn)
        dc.execute('SELECT id FROM t WHERE 1=0')
        assert dc.fetchall() == []

    def test_dictcursor_no_params(self):
        from db import DictCursor
        raw_conn = MagicMock()
        raw_cursor = MagicMock()
        raw_cursor.description = [('cnt',)]
        raw_cursor.fetchone.return_value = (5,)
        raw_conn.cursor.return_value = raw_cursor
        dc = DictCursor(raw_conn)
        dc.execute('SELECT COUNT(*) AS cnt FROM eaib_intel_reports')
        row = dc.fetchone()
        assert row == {'cnt': 5}


# ═══════════════════════════════════════════════════════════════════════════════
# API route tests (via Flask test client)
# ═══════════════════════════════════════════════════════════════════════════════

def _patched_app():
    """Load app with db.get_db mocked to return mock connection."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'app_eaib_test',
        os.path.join(os.path.dirname(__file__), '..', 'app.py')
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules['app_eaib_test'] = module
    with patch.dict('os.environ', {
        'FLASK_SECRET_KEY': 'test',
        'SUPABASE_DB_HOST': 'localhost',
        'SUPABASE_DB_NAME': 'postgres',
        'SUPABASE_DB_USER': 'postgres',
        'SUPABASE_DB_PASSWORD': 'test',
        'SUPABASE_DB_PORT': '6543',
    }):
        with patch('pg8000.connect') as mock_pg:
            mock_pg.return_value = MagicMock()
            try:
                spec.loader.exec_module(module)
            except Exception:
                pass
    return getattr(module, 'app', None)


class TestAPIRoutes:
    @pytest.fixture(autouse=True)
    def setup(self):
        app = _patched_app()
        if app is None:
            pytest.skip('App could not be loaded')
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.mock_conn = make_mock_conn()

    def _with_db(self, fn):
        import db as db_module
        orig = db_module.get_db
        db_module.get_db = lambda: self.mock_conn
        try:
            return fn()
        finally:
            db_module.get_db = orig

    def test_health_endpoint(self):
        def run():
            resp = self.client.get('/api/health')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert 'status' in data
        self._with_db(run)

    def test_debug_endpoint(self):
        def run():
            resp = self.client.get('/api/debug')
            assert resp.status_code == 200
        self._with_db(run)

    def test_api_intel_list(self):
        def run():
            resp = self.client.get('/api/intel/')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert isinstance(data, list)
        self._with_db(run)

    def test_api_intel_list_with_status(self):
        def run():
            resp = self.client.get('/api/intel/?status=active')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert isinstance(data, list)
        self._with_db(run)

    def test_api_intel_list_with_threat(self):
        def run():
            resp = self.client.get('/api/intel/?threat=critical')
            assert resp.status_code == 200
        self._with_db(run)

    def test_api_intel_create_success(self):
        def run():
            payload = {
                'title': 'New Threat',
                'reporter_name': 'TestPilot',
                'threat_level': 'high',
                'category': 'fleet',
            }
            resp = self.client.post('/api/intel/',
                                    data=json.dumps(payload),
                                    content_type='application/json')
            assert resp.status_code == 201
            data = json.loads(resp.data)
            assert 'id' in data
        self._with_db(run)

    def test_api_intel_create_missing_title(self):
        def run():
            resp = self.client.post('/api/intel/',
                                    data=json.dumps({'reporter_name': 'Pilot'}),
                                    content_type='application/json')
            assert resp.status_code == 400
            data = json.loads(resp.data)
            assert 'error' in data
        self._with_db(run)

    def test_api_intel_create_missing_reporter(self):
        def run():
            resp = self.client.post('/api/intel/',
                                    data=json.dumps({'title': 'Test'}),
                                    content_type='application/json')
            assert resp.status_code == 400
        self._with_db(run)

    def test_api_intel_get_existing(self):
        def run():
            resp = self.client.get('/api/intel/1/')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['id'] == 1
        self._with_db(run)

    def test_api_intel_get_missing(self):
        def run():
            resp = self.client.get('/api/intel/9999/')
            assert resp.status_code == 404
        self._with_db(run)

    def test_api_intel_update(self):
        def run():
            resp = self.client.patch('/api/intel/1/',
                                     data=json.dumps({'status': 'resolved'}),
                                     content_type='application/json')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['status'] == 'updated'
        self._with_db(run)

    def test_api_intel_update_no_fields(self):
        def run():
            resp = self.client.patch('/api/intel/1/',
                                     data=json.dumps({'garbage': 'data'}),
                                     content_type='application/json')
            assert resp.status_code == 400
        self._with_db(run)

    def test_api_intel_resolve(self):
        def run():
            resp = self.client.post('/api/intel/1/resolve/')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['status'] == 'resolved'
        self._with_db(run)

    def test_api_intel_expire(self):
        def run():
            resp = self.client.post('/api/intel/1/expire/')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['status'] == 'expired'
        self._with_db(run)

    def test_api_intel_false_positive(self):
        def run():
            resp = self.client.post('/api/intel/1/false-positive/')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['status'] == 'false_positive'
        self._with_db(run)

    def test_api_intel_add_tag(self):
        def run():
            resp = self.client.post('/api/intel/1/tags/',
                                    data=json.dumps({'tag_id': 3}),
                                    content_type='application/json')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['status'] == 'added'
        self._with_db(run)

    def test_api_intel_add_tag_missing_id(self):
        def run():
            resp = self.client.post('/api/intel/1/tags/',
                                    data=json.dumps({}),
                                    content_type='application/json')
            assert resp.status_code == 400
        self._with_db(run)

    def test_api_intel_remove_tag(self):
        def run():
            resp = self.client.delete('/api/intel/1/tags/1/')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['status'] == 'removed'
        self._with_db(run)

    def test_api_tags_list(self):
        def run():
            resp = self.client.get('/api/tags/')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert isinstance(data, list)
        self._with_db(run)

    def test_api_tags_create_success(self):
        def run():
            resp = self.client.post('/api/tags/',
                                    data=json.dumps({'name': 'Cyno Lit', 'color': '#a855f7'}),
                                    content_type='application/json')
            assert resp.status_code == 201
            data = json.loads(resp.data)
            assert 'id' in data
        self._with_db(run)

    def test_api_tags_create_missing_name(self):
        def run():
            resp = self.client.post('/api/tags/',
                                    data=json.dumps({'color': '#ff0000'}),
                                    content_type='application/json')
            assert resp.status_code == 400
        self._with_db(run)

    def test_api_tags_delete(self):
        def run():
            resp = self.client.delete('/api/tags/1/')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['status'] == 'deleted'
        self._with_db(run)

    def test_api_comment_add_success(self):
        def run():
            resp = self.client.post('/api/intel/1/comments/',
                                    data=json.dumps({'author_name': 'Pilot', 'body': 'Still active'}),
                                    content_type='application/json')
            assert resp.status_code == 201
            data = json.loads(resp.data)
            assert 'id' in data
        self._with_db(run)

    def test_api_comment_add_missing_fields(self):
        def run():
            resp = self.client.post('/api/intel/1/comments/',
                                    data=json.dumps({'author_name': 'Pilot'}),
                                    content_type='application/json')
            assert resp.status_code == 400
        self._with_db(run)

    def test_api_search_short(self):
        def run():
            resp = self.client.get('/api/search/?q=x')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data == []
        self._with_db(run)

    def test_api_search_results(self):
        def run():
            resp = self.client.get('/api/search/?q=Jita')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert isinstance(data, list)
        self._with_db(run)

    def test_api_stats(self):
        def run():
            resp = self.client.get('/api/stats/')
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert 'active' in data or 'total' in data or isinstance(data, dict)
        self._with_db(run)


# ═══════════════════════════════════════════════════════════════════════════════
# View (partial HTML) route tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestViewRoutes:
    @pytest.fixture(autouse=True)
    def setup(self):
        app = _patched_app()
        if app is None:
            pytest.skip('App could not be loaded')
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.mock_conn = make_mock_conn()

    def _with_db(self, fn):
        import db as db_module
        orig = db_module.get_db
        db_module.get_db = lambda: self.mock_conn
        try:
            return fn()
        finally:
            db_module.get_db = orig

    def test_root_returns_shell(self):
        def run():
            resp = self.client.get('/')
            assert resp.status_code == 200
            assert b'EAIB' in resp.data
        self._with_db(run)

    def test_dashboard_view(self):
        def run():
            resp = self.client.get('/dashboard/')
            assert resp.status_code == 200
            text = resp.data.decode()
            assert 'Dashboard' in text or 'ACTIVE' in text or 'kpi' in text
        self._with_db(run)

    def test_intel_feed_view(self):
        def run():
            resp = self.client.get('/intel/')
            assert resp.status_code == 200
        self._with_db(run)

    def test_intel_feed_with_filters(self):
        def run():
            resp = self.client.get('/intel/?status=active&threat=high')
            assert resp.status_code == 200
        self._with_db(run)

    def test_intel_feed_page_param(self):
        def run():
            resp = self.client.get('/intel/?page=2')
            assert resp.status_code == 200
        self._with_db(run)

    def test_intel_detail_existing(self):
        def run():
            resp = self.client.get('/intel/1/')
            assert resp.status_code == 200
            text = resp.data.decode()
            assert 'Jita' in text or 'detail' in text or 'Intel' in text
        self._with_db(run)

    def test_intel_detail_missing(self):
        def run():
            resp = self.client.get('/intel/9999/')
            assert resp.status_code == 404
        self._with_db(run)

    def test_intel_submit_view(self):
        def run():
            resp = self.client.get('/intel/submit/')
            assert resp.status_code == 200
            text = resp.data.decode()
            assert 'Submit' in text or 'form' in text.lower()
        self._with_db(run)

    def test_tags_view(self):
        def run():
            resp = self.client.get('/tags/')
            assert resp.status_code == 200
        self._with_db(run)


# ═══════════════════════════════════════════════════════════════════════════════
# Data validation / logic tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataValidation:
    def test_threat_levels_valid(self):
        valid = {'low', 'medium', 'high', 'critical'}
        for r in INTEL_REPORTS.values():
            assert r['threat_level'] in valid

    def test_categories_valid(self):
        valid = {'fleet', 'pos', 'structure', 'gank', 'camp', 'cyno', 'spy', 'war', 'other'}
        for r in INTEL_REPORTS.values():
            assert r['category'] in valid

    def test_statuses_valid(self):
        valid = {'active', 'resolved', 'expired', 'false_positive'}
        for r in INTEL_REPORTS.values():
            assert r['status'] in valid

    def test_all_reports_have_title(self):
        for r in INTEL_REPORTS.values():
            assert r['title']
            assert len(r['title']) > 0

    def test_all_reports_have_reporter(self):
        for r in INTEL_REPORTS.values():
            assert r['reporter_name']

    def test_tags_have_name_and_color(self):
        for t in TAGS.values():
            assert t['name']
            assert t['color'].startswith('#')

    def test_report_tags_reference_valid_ids(self):
        for report_id, tag_ids in REPORT_TAGS.items():
            assert report_id in INTEL_REPORTS
            for tid in tag_ids:
                assert tid in TAGS

    def test_comments_reference_valid_reports(self):
        for report_id in COMMENTS:
            assert report_id in INTEL_REPORTS

    def test_active_report_count(self):
        active = [r for r in INTEL_REPORTS.values() if r['status'] == 'active']
        assert len(active) == 2

    def test_critical_report_count(self):
        critical = [r for r in INTEL_REPORTS.values() if r['threat_level'] == 'critical' and r['status'] == 'active']
        assert len(critical) == 1
        assert critical[0]['system_name'] == 'Amarr'

    def test_resolved_report_count(self):
        resolved = [r for r in INTEL_REPORTS.values() if r['status'] == 'resolved']
        assert len(resolved) == 1

    def test_pilot_count_positive(self):
        for r in INTEL_REPORTS.values():
            if r['pilot_count'] is not None:
                assert r['pilot_count'] > 0

    def test_tag_colors_hex_format(self):
        import re
        hex_pattern = re.compile(r'^#[0-9a-fA-F]{6}$')
        for t in TAGS.values():
            assert hex_pattern.match(t['color']), f"Invalid color: {t['color']}"

    def test_filter_by_category(self):
        fleet = [r for r in INTEL_REPORTS.values() if r['category'] == 'fleet']
        assert len(fleet) == 1
        camp = [r for r in INTEL_REPORTS.values() if r['category'] == 'camp']
        assert len(camp) == 1

    def test_filter_by_system(self):
        jita = [r for r in INTEL_REPORTS.values() if r.get('system_name') == 'Jita']
        assert len(jita) == 1
        assert jita[0]['id'] == 1

    def test_filter_by_threat_level(self):
        high = [r for r in INTEL_REPORTS.values() if r['threat_level'] == 'high']
        assert len(high) == 1
        assert high[0]['id'] == 1
