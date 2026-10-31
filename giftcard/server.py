"""Local Gmail PIN workbench. Python standard library only."""
import argparse
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from google_auth import OAuth, CONFIG, configuration, validate_config
from extract import extract, workbook

ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()
TOKEN = secrets.token_urlsafe(32)
CLIENT = None
AUTH = OAuth()
RESUME = threading.Event()
RESUME.set()
STATE = dict(account='', connected=False, busy=False, query='', ids=[], cursor=0,
             rows=[], error='', progress=0, batch_total=0, searched=False, source='',
             batch_running=False, pause_requested=False, paused=False)


def search(query):
    ids = CLIENT.search(query)
    with LOCK:
        STATE.update(query=query, ids=ids, cursor=0, rows=[], searched=True,
                     progress=0, batch_total=0, source='Gmail API · 只读授权')


def fetch_batch(ids, retry=False):
    with LOCK:
        STATE.update(progress=0, batch_total=len(ids), batch_running=True)
    for uid in ids:
        with LOCK:
            STATE['paused'] = STATE['pause_requested']
        RESUME.wait()
        with LOCK:
            STATE['paused'] = False
        try:
            raw = CLIENT.read(uid)
            rows = extract(raw, uid)
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ValueError) else '读取失败，请检查网络并重试。'
            rows = [dict(uid=uid, pin='', status='读取失败', error=reason)]
        with LOCK:
            if retry:
                STATE['rows'] = [r for r in STATE['rows'] if r['uid'] != uid]
            STATE['rows'].extend(rows)
            STATE['progress'] += 1
            if not retry:
                STATE['cursor'] += 1


def run_job(fn, *args):
    try:
        fn(*args)
    except Exception as exc:
        with LOCK:
            STATE['error'] = str(exc) if isinstance(exc, ValueError) else '网络连接失败，请稍后重新连接。'
    finally:
        with LOCK:
            STATE.update(busy=False, batch_running=False, paused=False, pause_requested=False)
            RESUME.set()


def logout_quietly(client):
    try:
        client.logout()
    except Exception:
        pass


def snapshot():
    with LOCK:
        result = {key: value for key, value in STATE.items() if key != 'ids'}
        result['total'] = len(STATE['ids'])
        result['token'] = TOKEN
        try:
            configuration()
            result['oauth_configured'] = True
        except ValueError:
            result['oauth_configured'] = False
        # JSON serialization takes place under lock for a consistent snapshot.
        return json.dumps(result, ensure_ascii=False).encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Never log PINs, search terms or credentials.

    def allowed(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def reply(self, data, content_type='application/json; charset=utf-8', status=200, download=False):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if download:
            self.send_header('Content-Disposition', 'attachment; filename="gift-card-pins.xlsx"')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        global CLIENT
        if not self.allowed():
            return self.reply(b'{}', status=403)
        path = urlparse(self.path).path
        if path == '/oauth/callback':
            params = {key: values[0] for key, values in parse_qs(urlparse(self.path).query).items()}
            reserved = False
            try:
                with LOCK:
                    if STATE['busy']:
                        raise ValueError('后台正在处理邮件，请稍后重新登录。')
                    pending = AUTH.consume(params)
                    STATE['busy'] = True
                    reserved = True
                client, account = AUTH.finish(params, pending)
                with LOCK:
                    if CLIENT:
                        CLIENT.logout()
                    CLIENT = client
                    STATE.update(account=account, connected=True, rows=[], ids=[], cursor=0,
                                 query='', searched=False, error='', progress=0, batch_total=0,
                                 source='Gmail API · 只读授权')
            except Exception as exc:
                with LOCK:
                    STATE['error'] = str(exc) if isinstance(exc, ValueError) else 'Google 登录未完成，请检查网络后重试。'
            finally:
                if reserved:
                    with LOCK:
                        STATE['busy'] = False
            self.send_response(303)
            self.send_header('Location', '/')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if path == '/favicon.ico':
            return self.reply(b'', 'image/x-icon', status=204)
        if path == '/api/state':
            return self.reply(snapshot())
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in assets:
            return self.reply(b'{}', status=404)
        name, mime = assets[path]
        self.reply((ROOT / 'web' / name).read_bytes(), mime)

    def do_POST(self):
        global CLIENT
        origin = self.headers.get('Origin')
        if (not self.allowed() or self.headers.get('X-Token') != TOKEN
                or (origin and origin != f'http://127.0.0.1:{self.server.server_port}')):
            return self.reply(b'{}', status=403)
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 16384:
                raise ValueError('请求大小无效。')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('请求格式无效。')
            with LOCK:
                if self.path in ('/api/pause', '/api/resume'):
                    if not STATE['batch_running']:
                        raise ValueError('当前没有正在提取的批次。')
                    if self.path == '/api/pause':
                        STATE['pause_requested'] = True
                        RESUME.clear()
                    else:
                        STATE.update(pause_requested=False, paused=False)
                        RESUME.set()
                    return self.reply(b'{}')
                if self.path == '/api/export':
                    rows = list(STATE['rows'])
                    if not rows:
                        raise ValueError('当前没有可导出的结果。')
                    return self.reply(workbook(rows), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', download=True)
                if STATE['busy']:
                    raise ValueError('正在处理，请等待当前操作完成。')
                if self.path == '/api/oauth/config':
                    config = validate_config(body.get('config'))
                    CONFIG.parent.mkdir(exist_ok=True)
                    temp = CONFIG.with_suffix('.tmp')
                    temp.write_text(json.dumps({'installed': config}), encoding='utf-8')
                    temp.replace(CONFIG)
                    AUTH.pending = None
                    return self.reply(b'{}')
                elif self.path == '/api/oauth/start':
                    url = AUTH.begin(self.server.server_port, str(body.get('account', '')).strip()[:320])
                    return self.reply(json.dumps({'url': url}).encode())
                elif self.path == '/api/disconnect':
                    AUTH.pending = None
                    old, CLIENT = CLIENT, None
                    if old:
                        threading.Thread(target=logout_quietly, args=(old,), daemon=True).start()
                    STATE.update(account='', connected=False, rows=[], ids=[], cursor=0,
                                 query='', searched=False, error='', source='', progress=0, batch_total=0)
                    return self.reply(b'{}')
                elif self.path == '/api/search':
                    if not STATE['connected']:
                        raise ValueError('请先连接 Gmail。')
                    query = str(body.get('query', '')).strip()
                    if not query or len(query) > 2048 or any(c in query for c in '\r\n\x00'):
                        raise ValueError('请输入有效 Filter（1–2048 个字符）。')
                    fn, args = search, (query,)
                elif self.path in ('/api/batch', '/api/retry'):
                    if not STATE['connected'] or not STATE['searched']:
                        raise ValueError('请先连接并搜索邮件。')
                    count = body.get('count', 100)
                    if type(count) is not int or not 1 <= count <= 100:
                        raise ValueError('每批需为 1–100 封邮件。')
                    retry = self.path == '/api/retry'
                    ids = list(dict.fromkeys(r['uid'] for r in STATE['rows'] if r['status'] == '读取失败'))[:count] if retry else STATE['ids'][STATE['cursor']:STATE['cursor']+count]
                    if not ids:
                        raise ValueError('没有待处理的邮件。')
                    fn, args = fetch_batch, (ids, retry)
                else:
                    return self.reply(b'{}', status=404)
                STATE.update(busy=True, error='', pause_requested=False, paused=False)
                RESUME.set()
                threading.Thread(target=run_job, args=(fn, *args), daemon=True).start()
            self.reply(b'{}', status=202)
        except (ValueError, TypeError) as exc:
            self.reply(json.dumps({'error': str(exc)}, ensure_ascii=False).encode(), status=400)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8876)
    parser.add_argument('--import-messages', type=Path, help='Import a locally saved Gmail connector MIME JSON snapshot')
    parser.add_argument('--restore-results', type=Path, help='Restore exported local result rows after an update; does not restore login')
    args = parser.parse_args()
    if args.restore_results:
        saved = json.loads(args.restore_results.read_text(encoding='utf-8-sig'))
        STATE.update(rows=saved['rows'], source='更新前的提取结果 · 重新登录后可搜索邮件')
    if args.import_messages:
        from email.message import EmailMessage
        messages = json.loads(args.import_messages.read_text(encoding='utf-8'))
        for item in messages:
            msg = EmailMessage()
            for key in ('Subject', 'From', 'Date'):
                msg[key] = next((h['value'] for h in item['payload']['headers'] if h['name'].lower() == key.lower()), '')
            def walk(part):
                if part.get('mime_type') in ('text/html', 'text/plain') and part.get('body', {}).get('content'):
                    msg.add_alternative(part['body']['content'], subtype=part['mime_type'].split('/')[1])
                for child in part.get('parts') or []:
                    walk(child)
            walk(item['payload'])
            STATE['rows'].extend(extract(msg.as_bytes(), item['id']))
        STATE['source'] = f'已导入 {len(messages)} 封邮件快照 · 连接 Gmail 后可继续搜索'
    print(f'Gift Card PIN: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
