from flask import Blueprint, render_template
import db as _db

bp = Blueprint('dashboard', __name__)


@bp.route('/dashboard/')
def dashboard():
    conn = _db.get_db()
    try:
        cur = conn.cursor()

        # Total active threats
        cur.execute("SELECT COUNT(*) AS cnt FROM eaib_intel_reports WHERE status='active'")
        active_count = cur.fetchone()['cnt']

        # Critical threats
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM eaib_intel_reports "
            "WHERE status='active' AND threat_level='critical'"
        )
        critical_count = cur.fetchone()['cnt']

        # Resolved today
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM eaib_intel_reports "
            "WHERE status='resolved' AND updated_at >= CURRENT_DATE"
        )
        resolved_today = cur.fetchone()['cnt']

        # Total reports all-time
        cur.execute("SELECT COUNT(*) AS cnt FROM eaib_intel_reports")
        total_reports = cur.fetchone()['cnt']

        # Threat distribution by level (active only)
        cur.execute("""
            SELECT threat_level, COUNT(*) AS cnt
            FROM eaib_intel_reports
            WHERE status = 'active'
            GROUP BY threat_level
            ORDER BY CASE threat_level
                WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END
        """)
        threat_dist = cur.fetchall()

        # Category breakdown (active)
        cur.execute("""
            SELECT category, COUNT(*) AS cnt
            FROM eaib_intel_reports
            WHERE status = 'active'
            GROUP BY category
            ORDER BY cnt DESC
        """)
        category_dist = cur.fetchall()

        # Top systems by active report count
        cur.execute("""
            SELECT system_name, region_name,
                   COUNT(*) AS report_count,
                   MAX(CASE WHEN threat_level='critical' THEN 4
                            WHEN threat_level='high'     THEN 3
                            WHEN threat_level='medium'   THEN 2
                            ELSE 1 END) AS max_threat_num,
                   MAX(threat_level) AS top_threat
            FROM eaib_intel_reports
            WHERE status = 'active' AND system_name IS NOT NULL
            GROUP BY system_name, region_name
            ORDER BY max_threat_num DESC, report_count DESC
            LIMIT 10
        """)
        hot_systems = cur.fetchall()

        # Recent intel feed (last 20 active)
        cur.execute("""
            SELECT r.id, r.title, r.system_name, r.region_name,
                   r.reporter_name, r.threat_level, r.category,
                   r.status, r.ship_type, r.pilot_count, r.created_at,
                   (SELECT COUNT(*) FROM eaib_comments c WHERE c.report_id = r.id) AS comment_count
            FROM eaib_intel_reports r
            WHERE r.status = 'active'
            ORDER BY r.created_at DESC
            LIMIT 20
        """)
        recent_intel = cur.fetchall()

        # Active reports by region
        cur.execute("""
            SELECT region_name, COUNT(*) AS cnt,
                   SUM(CASE WHEN threat_level='critical' THEN 1 ELSE 0 END) AS critical_cnt
            FROM eaib_intel_reports
            WHERE status = 'active' AND region_name IS NOT NULL
            GROUP BY region_name
            ORDER BY cnt DESC
            LIMIT 12
        """)
        region_breakdown = cur.fetchall()

        cur.close()
    finally:
        conn.close()

    return render_template(
        'partials/dashboard/index.html',
        active_count=active_count,
        critical_count=critical_count,
        resolved_today=resolved_today,
        total_reports=total_reports,
        threat_dist=threat_dist,
        category_dist=category_dist,
        hot_systems=hot_systems,
        recent_intel=recent_intel,
        region_breakdown=region_breakdown,
    )
