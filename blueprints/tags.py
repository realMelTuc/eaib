from flask import Blueprint, render_template
import db as _db

bp = Blueprint('tags', __name__)


@bp.route('/tags/')
def tags_index():
    conn = _db.get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.id, t.name, t.color, t.description, t.created_at,
                   COUNT(rt.report_id) AS report_count
            FROM eaib_tags t
            LEFT JOIN eaib_report_tags rt ON rt.tag_id = t.id
            GROUP BY t.id, t.name, t.color, t.description, t.created_at
            ORDER BY report_count DESC, t.name
        """)
        tags = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    return render_template('partials/tags/index.html', tags=tags)
