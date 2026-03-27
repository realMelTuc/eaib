from flask import Blueprint, render_template, request
import db as _db

bp = Blueprint('intel', __name__)

PAGE_SIZE = 30


@bp.route('/intel/')
def intel_feed():
    threat = request.args.get('threat', '')
    category = request.args.get('category', '')
    status_filter = request.args.get('status', 'active')
    system = request.args.get('system', '')
    region = request.args.get('region', '')
    tag_id = request.args.get('tag', '')
    page = max(1, int(request.args.get('page', 1)))
    offset = (page - 1) * PAGE_SIZE

    conn = _db.get_db()
    try:
        cur = conn.cursor()

        # Build WHERE clauses
        conditions = []
        params = []

        if status_filter:
            conditions.append('r.status = %s')
            params.append(status_filter)
        if threat:
            conditions.append('r.threat_level = %s')
            params.append(threat)
        if category:
            conditions.append('r.category = %s')
            params.append(category)
        if system:
            conditions.append('r.system_name ILIKE %s')
            params.append(f'%{system}%')
        if region:
            conditions.append('r.region_name ILIKE %s')
            params.append(f'%{region}%')
        if tag_id:
            conditions.append(
                'EXISTS (SELECT 1 FROM eaib_report_tags rt WHERE rt.report_id=r.id AND rt.tag_id=%s)'
            )
            params.append(int(tag_id))

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

        # Count
        cur.execute(f'SELECT COUNT(*) AS cnt FROM eaib_intel_reports r {where}', params)
        total = cur.fetchone()['cnt']
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

        # Rows
        cur.execute(f"""
            SELECT r.id, r.title, r.system_name, r.region_name,
                   r.reporter_name, r.threat_level, r.category,
                   r.status, r.ship_type, r.pilot_count,
                   r.created_at, r.updated_at,
                   (SELECT COUNT(*) FROM eaib_comments c WHERE c.report_id=r.id) AS comment_count
            FROM eaib_intel_reports r
            {where}
            ORDER BY r.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [PAGE_SIZE, offset])
        reports = cur.fetchall()

        # All tags for filter dropdown
        cur.execute('SELECT id, name, color FROM eaib_tags ORDER BY name')
        all_tags = cur.fetchall()

        cur.close()
    finally:
        conn.close()

    return render_template(
        'partials/intel/feed.html',
        reports=reports,
        total=total,
        page=page,
        total_pages=total_pages,
        page_size=PAGE_SIZE,
        threat=threat,
        category=category,
        status_filter=status_filter,
        system=system,
        region=region,
        tag_id=tag_id,
        all_tags=all_tags,
    )


@bp.route('/intel/<int:report_id>/')
def intel_detail(report_id):
    conn = _db.get_db()
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT id, title, system_name, region_name,
                   reporter_name, character_name, corporation_name, alliance_name,
                   threat_level, category, status, description, raw_text,
                   ship_type, pilot_count, created_at, updated_at, expires_at
            FROM eaib_intel_reports WHERE id = %s
        """, [report_id])
        report = cur.fetchone()

        if not report:
            return '<p style="color:#ef4444;padding:20px">Report not found.</p>', 404

        # Tags
        cur.execute("""
            SELECT t.id, t.name, t.color
            FROM eaib_tags t
            JOIN eaib_report_tags rt ON rt.tag_id = t.id
            WHERE rt.report_id = %s
            ORDER BY t.name
        """, [report_id])
        tags = cur.fetchall()

        # All available tags for edit
        cur.execute('SELECT id, name, color FROM eaib_tags ORDER BY name')
        all_tags = cur.fetchall()

        # Comments
        cur.execute("""
            SELECT id, author_name, body, created_at
            FROM eaib_comments
            WHERE report_id = %s
            ORDER BY created_at ASC
        """, [report_id])
        comments = cur.fetchall()

        # Related: same system, same category, recent
        cur.execute("""
            SELECT id, title, threat_level, category, created_at
            FROM eaib_intel_reports
            WHERE id != %s
              AND (system_name = %s OR category = %s)
              AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 5
        """, [report_id, report.get('system_name'), report.get('category')])
        related = cur.fetchall()

        cur.close()
    finally:
        conn.close()

    return render_template(
        'partials/intel/detail.html',
        report=report,
        tags=tags,
        all_tags=all_tags,
        comments=comments,
        related=related,
    )


@bp.route('/intel/submit/')
def intel_submit():
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, name, color FROM eaib_tags ORDER BY name')
        all_tags = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    return render_template('partials/intel/submit.html', all_tags=all_tags)
