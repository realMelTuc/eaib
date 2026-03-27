from flask import Blueprint, jsonify, request
import db as _db
from db import serialize_row

bp = Blueprint('api', __name__)


# ── Intel Reports ─────────────────────────────────────────────────────────────

@bp.route('/api/intel/', methods=['GET'])
def api_intel_list():
    threat = request.args.get('threat', '')
    category = request.args.get('category', '')
    status_filter = request.args.get('status', 'active')
    limit = min(int(request.args.get('limit', 50)), 200)

    conn = _db.get_db()
    try:
        cur = conn.cursor()
        conditions = []
        params = []
        if status_filter:
            conditions.append('status = %s')
            params.append(status_filter)
        if threat:
            conditions.append('threat_level = %s')
            params.append(threat)
        if category:
            conditions.append('category = %s')
            params.append(category)
        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        cur.execute(
            f'SELECT * FROM eaib_intel_reports {where} ORDER BY created_at DESC LIMIT %s',
            params + [limit]
        )
        rows = [serialize_row(r) for r in cur.fetchall()]
        cur.close()
    finally:
        conn.close()
    return jsonify(rows)


@bp.route('/api/intel/', methods=['POST'])
def api_intel_create():
    data = request.get_json(force=True) or {}
    required = ('title', 'reporter_name')
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} is required'}), 400

    conn = _db.get_db()
    try:
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
            data['title'],
            data.get('system_name') or None,
            data.get('region_name') or None,
            data['reporter_name'],
            data.get('character_name') or None,
            data.get('corporation_name') or None,
            data.get('alliance_name') or None,
            data.get('threat_level', 'medium'),
            data.get('category', 'other'),
            data.get('status', 'active'),
            data.get('description') or None,
            data.get('raw_text') or None,
            data.get('ship_type') or None,
            int(data['pilot_count']) if data.get('pilot_count') else None,
            data.get('expires_at') or None,
        ])
        row = cur.fetchone()
        new_id = row['id']

        # Attach tags
        tag_ids = data.get('tag_ids', [])
        for tid in tag_ids:
            cur.execute(
                'INSERT INTO eaib_report_tags (report_id, tag_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                [new_id, int(tid)]
            )

        conn.commit()
        cur.close()
    finally:
        conn.close()

    return jsonify({'id': new_id, 'status': 'created'}), 201


@bp.route('/api/intel/<int:report_id>/', methods=['GET'])
def api_intel_get(report_id):
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM eaib_intel_reports WHERE id = %s', [report_id])
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        result = serialize_row(row)

        cur.execute("""
            SELECT t.id, t.name, t.color
            FROM eaib_tags t JOIN eaib_report_tags rt ON rt.tag_id=t.id
            WHERE rt.report_id = %s
        """, [report_id])
        result['tags'] = cur.fetchall()

        cur.close()
    finally:
        conn.close()
    return jsonify(result)


@bp.route('/api/intel/<int:report_id>/', methods=['PATCH'])
def api_intel_update(report_id):
    data = request.get_json(force=True) or {}
    allowed = {
        'title', 'system_name', 'region_name', 'reporter_name',
        'character_name', 'corporation_name', 'alliance_name',
        'threat_level', 'category', 'status', 'description',
        'raw_text', 'ship_type', 'pilot_count', 'expires_at',
    }
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return jsonify({'error': 'no valid fields'}), 400

    set_clause = ', '.join(f'{k} = %s' for k in fields)
    values = list(fields.values()) + ['NOW()', report_id]

    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            f'UPDATE eaib_intel_reports SET {set_clause}, updated_at = %s WHERE id = %s',
            values
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'status': 'updated'})


@bp.route('/api/intel/<int:report_id>/resolve/', methods=['POST'])
def api_intel_resolve(report_id):
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE eaib_intel_reports SET status='resolved', updated_at=NOW() WHERE id=%s",
            [report_id]
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'status': 'resolved'})


@bp.route('/api/intel/<int:report_id>/expire/', methods=['POST'])
def api_intel_expire(report_id):
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE eaib_intel_reports SET status='expired', updated_at=NOW() WHERE id=%s",
            [report_id]
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'status': 'expired'})


@bp.route('/api/intel/<int:report_id>/false-positive/', methods=['POST'])
def api_intel_false_positive(report_id):
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE eaib_intel_reports SET status='false_positive', updated_at=NOW() WHERE id=%s",
            [report_id]
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'status': 'false_positive'})


# ── Tags ──────────────────────────────────────────────────────────────────────

@bp.route('/api/tags/', methods=['GET'])
def api_tags_list():
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM eaib_tags ORDER BY name')
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    return jsonify(rows)


@bp.route('/api/tags/', methods=['POST'])
def api_tags_create():
    data = request.get_json(force=True) or {}
    if not data.get('name'):
        return jsonify({'error': 'name is required'}), 400

    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO eaib_tags (name, color, description) VALUES (%s,%s,%s) RETURNING id',
            [data['name'], data.get('color', '#00d4aa'), data.get('description') or None]
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'id': row['id'], 'status': 'created'}), 201


@bp.route('/api/tags/<int:tag_id>/', methods=['DELETE'])
def api_tags_delete(tag_id):
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM eaib_tags WHERE id = %s', [tag_id])
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'status': 'deleted'})


# ── Report tags ───────────────────────────────────────────────────────────────

@bp.route('/api/intel/<int:report_id>/tags/', methods=['POST'])
def api_report_tag_add(report_id):
    data = request.get_json(force=True) or {}
    tag_id = data.get('tag_id')
    if not tag_id:
        return jsonify({'error': 'tag_id required'}), 400
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO eaib_report_tags (report_id, tag_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
            [report_id, int(tag_id)]
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'status': 'added'})


@bp.route('/api/intel/<int:report_id>/tags/<int:tag_id>/', methods=['DELETE'])
def api_report_tag_remove(report_id, tag_id):
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            'DELETE FROM eaib_report_tags WHERE report_id=%s AND tag_id=%s',
            [report_id, tag_id]
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'status': 'removed'})


# ── Comments ─────────────────────────────────────────────────────────────────

@bp.route('/api/intel/<int:report_id>/comments/', methods=['POST'])
def api_comment_add(report_id):
    data = request.get_json(force=True) or {}
    if not data.get('author_name') or not data.get('body'):
        return jsonify({'error': 'author_name and body required'}), 400
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO eaib_comments (report_id, author_name, body) VALUES (%s,%s,%s) RETURNING id',
            [report_id, data['author_name'], data['body']]
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'id': row['id'], 'status': 'added'}), 201


# ── Search ───────────────────────────────────────────────────────────────────

@bp.route('/api/search/')
def api_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, system_name, region_name, threat_level, status
            FROM eaib_intel_reports
            WHERE title ILIKE %s OR system_name ILIKE %s OR character_name ILIKE %s
            ORDER BY created_at DESC
            LIMIT 10
        """, [f'%{q}%', f'%{q}%', f'%{q}%'])
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    return jsonify(rows)


# ── Stats ─────────────────────────────────────────────────────────────────────

@bp.route('/api/stats/')
def api_stats():
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status='active') AS active,
                COUNT(*) FILTER (WHERE status='active' AND threat_level='critical') AS critical,
                COUNT(*) FILTER (WHERE status='resolved' AND updated_at >= CURRENT_DATE) AS resolved_today,
                COUNT(*) AS total
            FROM eaib_intel_reports
        """)
        stats = cur.fetchone()
        cur.close()
    finally:
        conn.close()
    return jsonify(dict(stats))
