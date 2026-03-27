import os
import sys
import traceback

try:
    from dotenv import load_dotenv
    from flask import Flask, jsonify, render_template, request
    from db import get_db
    load_dotenv('.env.eaib')
    _BOOT_ERROR = None
except Exception as _e:
    _BOOT_ERROR = traceback.format_exc()
    from flask import Flask, jsonify
    def get_db(): raise RuntimeError('DB not available')
    def render_template(*a, **kw): return f'<pre>Boot error:\n{_BOOT_ERROR}</pre>'
    class _R:
        path = ''
        method = ''
        endpoint = ''
        headers = {}
        remote_addr = ''
        args = {}
    request = _R()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'eaib-dev-key-change-in-prod')

if _BOOT_ERROR:
    @app.route('/')
    @app.route('/<path:p>')
    def boot_error(p=''):
        return (
            f'<pre style="background:#0d1117;color:#ef4444;padding:20px;'
            f'font-family:monospace">EAIB Boot Error:\n\n{_BOOT_ERROR}</pre>'
        ), 500

# Ensure local blueprints package is used
blueprints_dir = os.path.join(os.path.dirname(__file__), 'blueprints')
sys.path.insert(0, os.path.dirname(__file__))

# Auto-discover and register blueprints
_bp_errors = []
if not _BOOT_ERROR:
    import importlib.util
    for filename in sorted(os.listdir(blueprints_dir)):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]
            try:
                spec = importlib.util.spec_from_file_location(
                    module_name, os.path.join(blueprints_dir, filename)
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'bp'):
                    app.register_blueprint(module.bp)
            except Exception as e:
                _bp_errors.append(f'{filename}: {e}')


@app.errorhandler(Exception)
def handle_global_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    tb = traceback.format_exc()
    print(f'EAIB ERROR: {e}\n{tb}')
    if request.path.startswith('/api/'):
        return jsonify({'error': str(e)}), 500
    return f'<pre style="color:#ef4444;background:#0d1117;padding:20px">{tb}</pre>', 500


@app.route('/')
def index():
    return render_template('shell.html')


@app.route('/api/health')
def health_check():
    result = {'status': 'ok', 'python': sys.version, 'bp_errors': _bp_errors}
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('SELECT 1 AS ok')
        row = cur.fetchone()
        result['db'] = 'connected' if row else 'no_result'
        cur.close()
        conn.close()
    except Exception as e:
        result['db'] = f'error: {e}'
        result['status'] = 'db_error'
    return jsonify(result)


@app.route('/api/debug')
def debug_info():
    return jsonify({
        'boot_error': _BOOT_ERROR,
        'blueprint_errors': _bp_errors,
        'env_keys': [k for k in os.environ if any(x in k for x in ('SUPA', 'FLASK', 'VERCEL', 'EAIB'))],
    })


if __name__ == '__main__':
    app.run(
        host='0.0.0.0', port=5015,
        debug=os.environ.get('FLASK_DEBUG', '0') == '1',
        use_reloader=False,
    )
