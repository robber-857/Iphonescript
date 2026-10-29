from pathlib import Path
ROOT = Path(__file__).resolve().parent
import ctypes
import json
import os
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from monitor import VARIANTS, STORES, stock_changes, MODELS, variants_for
from phone import Phone

DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
STATE_FILE = DATA / 'state.json'
LOCK = threading.RLock()
WAKE = threading.Event()
TOKEN = secrets.token_urlsafe(32)
STATE = dict(enabled=False, interval=300, notifications=True, running=False,
             next_check=None, current=None, results={}, events=[], last_cycle=None)
if STATE_FILE.exists():
    try:
        STATE.update(json.loads(STATE_FILE.read_text(encoding='utf-8')))
    except (ValueError, OSError):
        pass
STATE.update(running=False, current=None, next_check=time.time() if STATE['enabled'] else None)
STATE.update(collector_seen=None,task=None,queue=[])
STATE.setdefault('postcode','2000')
STATE.setdefault('model','duo')
STATE.setdefault('clear_apple_cookies',False)
STATE.setdefault('cookie_cleanup',None)
PHONE = Phone(DATA)
PENDING_PHONE = []

def phone_report(message):
    with LOCK:
        event('phone', message)
        save()

def finish_phone_cycle():
    if PENDING_PHONE:
        try:
            PHONE.call('iPhone stock alert. '+ '; '.join(PENDING_PHONE[:5]) + '. Please check the Apple website now.', phone_report)
        except ValueError as exc:
            event('phone', str(exc))
        PENDING_PHONE.clear()

def save():
    tmp = DATA / 'state.tmp'
    tmp.write_text(json.dumps(STATE,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(STATE_FILE)

def event(kind, message):
    STATE['events'].insert(0, dict(time=time.time(), kind=kind, message=message))
    STATE['events'] = STATE['events'][:200]

def notify(message):
    def show():
        if os.name == 'nt':
            import winsound
            for _ in range(3):
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                time.sleep(.4)
            ctypes.windll.user32.MessageBoxW(0,message,'iPhone Duo 库存提醒',0x40 | 0x1000)
        else:
            print('\a'+message,flush=True)
    threading.Thread(target=show,daemon=True).start()

class Handler(BaseHTTPRequestHandler):
    def send(self,status,body,content_type='application/json; charset=utf-8'):
        if not isinstance(body,bytes):
            body=json.dumps(body,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:8765','localhost:8765'):
            return self.send(403,{'error':'Local access only'})
        if self.path == '/api/state':
            with LOCK:
                return self.send(200,dict(STATE,variants=variants_for(STATE['model']),models=MODELS,phone=PHONE.status(),stores=STORES,token=TOKEN,server_time=time.time()))
        if self.path == '/api/collector/task':
            if self.headers.get('X-Duo-Token') != TOKEN:
                return self.send(403,{'error':'Reload collector token'})
            with LOCK:
                now=time.time()
                STATE['collector_seen']=now
                if STATE.get('cookie_cleanup') and STATE.get('clear_apple_cookies'):
                    return self.send(200,{'task':None,'cleanup':STATE['cookie_cleanup']})
                task=STATE.get('task')
                if task and now-task['started']>150:
                    result=STATE['results'].setdefault(task['variant']['id'],dict(stores=[],checked=None))
                    result.update(error='浏览器采集超时，请保持 Chrome 运行',attempted=now)
                    event('error',task['variant']['id']+'：浏览器采集超时')
                    STATE['task']=None
                if not STATE['enabled']:
                    STATE.update(queue=[],running=False,current=None,task=None)
                elif not STATE.get('task'):
                    if not STATE['running'] and now >= (STATE['next_check'] or 0):
                        PENDING_PHONE.clear()
                        STATE.update(queue=list(variants_for(STATE['model'])),running=True,next_check=None)
                    if STATE['queue']:
                        variant=STATE['queue'].pop(0)
                        STATE.update(task=dict(id=secrets.token_hex(12),variant=variant,postcode=STATE['postcode'],started=now),current=variant.get('model','iPhone Duo')+' '+variant['capacity']+' '+variant['colour'])
                    elif STATE['running']:
                        finish_phone_cycle()
                        STATE.update(running=False,current=None,last_cycle=now,next_check=now+STATE['interval'])
                        if STATE.get('clear_apple_cookies'):
                            STATE.update(cookie_cleanup=secrets.token_hex(12),next_check=None)
                save()
                return self.send(200,{'task':STATE.get('task'),'cleanup':STATE.get('cookie_cleanup')})
        files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
        if self.path not in files:
            return self.send(404,{'error':'Not found'})
        mime={'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}
        self.send(200,(ROOT/'web'/files[self.path]).read_bytes(),mime[self.path])

    def do_POST(self):
        if self.headers.get('X-Duo-Token') != TOKEN:
            return self.send(403,{'error':'请刷新页面后重试'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>4096:
                raise ValueError('请求过大')
            payload=json.loads(self.rfile.read(length) or b'{}')
            with LOCK:
                if self.path == '/api/start':
                    STATE.update(enabled=True,next_check=time.time())
                    event('info','已开启监测：'+MODELS[STATE['model']]+'，悉尼 7 家门店')
                elif self.path == '/api/pause':
                    STATE.update(enabled=False,next_check=None)
                    event('info','已暂停；正在进行的单个配置查询将完成后停止')
                elif self.path == '/api/check':
                    if STATE['running']:
                        return self.send(409,{'error':'正在检查，请等待当前轮次结束'})
                    STATE.update(enabled=True,next_check=time.time())
                elif self.path == '/api/settings':
                    interval=int(payload['interval'])
                    if interval not in (30,60,120,300):
                        raise ValueError('请选择支持的检查间隔')
                    if not isinstance(payload.get('notifications'),bool):
                        raise ValueError('提醒开关格式错误')
                    postcode=str(payload.get('postcode',STATE['postcode'])).strip()
                    if not re.fullmatch(r'[0-9]{4}',postcode):
                        raise ValueError('请输入四位澳洲邮编，例如 2000')
                    model=payload.get('model',STATE['model'])
                    if model not in MODELS:
                        raise ValueError('请选择支持的机型')
                    changed=postcode!=STATE['postcode'] or model!=STATE['model']
                    clear_cookies=payload.get('clear_apple_cookies',STATE.get('clear_apple_cookies',False))
                    if not isinstance(clear_cookies,bool):
                        raise ValueError('Cookie 清理开关格式错误')
                    STATE['clear_apple_cookies']=clear_cookies
                    if not clear_cookies:
                        STATE['cookie_cleanup']=None
                    STATE.update(interval=interval,notifications=payload['notifications'])
                    if changed:
                        PENDING_PHONE.clear()
                        STATE.update(postcode=postcode,model=model,results={},task=None,queue=[],running=False,current=None,
                                     next_check=time.time() if STATE['enabled'] else None)
                        event('info','监测配置：'+MODELS[model]+' / '+postcode+'，旧结果已清空')
                    elif STATE['enabled'] and not STATE['running']:
                        STATE['next_check']=time.time()+interval
                elif self.path == '/api/collector/cleanup':
                    if not STATE.get('cookie_cleanup') or payload.get('id')!=STATE['cookie_cleanup']:
                        return self.send(409,{'error':'Cleanup expired'})
                    error=bool(payload.get('error'))
                    event('error' if error else 'info','Apple Cookie 清理失败，监测已暂停，请检查扩展权限' if error else '整轮结束：Apple Cookie 清理完成，开始等待下一轮')
                    STATE.update(cookie_cleanup=None,next_check=time.time()+STATE['interval'] if STATE['enabled'] and not error else None)
                    if error:
                        STATE['enabled']=False
                elif self.path == '/api/phone/settings':
                    PHONE.configure(payload)
                elif self.path == '/api/phone/test':
                    if payload.get('confirm') is not True:
                        raise ValueError('请确认向已配置号码拨打测试电话')
                    PHONE.call('This is a test call from your iPhone stock monitor. This is not a stock alert.', phone_report, test=True)
                elif self.path == '/api/test-notification':
                    notify('这是一条测试提醒，不代表门店有货。')
                elif self.path == '/api/collector/result':
                    task=STATE.get('task')
                    if not task or payload.get('id')!=task['id']:
                        return self.send(409,{'error':'Task expired'})
                    if payload.get('postcode','2000')!=task.get('postcode','2000'):
                        return self.send(409,{'error':'采集结果邮编不匹配，请刷新采集扩展'})
                    variant=task['variant']
                    result=STATE['results'].setdefault(variant['id'],dict(stores=[],checked=None))
                    if payload.get('error'):
                        result.update(error=str(payload['error'])[:500],attempted=time.time())
                        event('error',variant['id']+'：'+str(payload['error'])[:220])
                    else:
                        rows=payload['stores']
                        if len(rows)!=len(STORES) or {r['store_id'] for r in rows}!=set(STORES):
                            raise ValueError('门店列表不完整')
                        if any(r['status'] not in ('available','unavailable') for r in rows):
                            raise ValueError('无法识别库存状态')
                        changes=stock_changes(result.get('stores',[]),rows)
                        STATE['results'][variant['id']]=dict(stores=rows,checked=time.time(),attempted=time.time(),error=None)
                        for row in changes:
                            msg=f"{variant.get('model','iPhone Duo')} · {row['store']} · {variant['capacity']} {variant['colour']} · {row['message']}"
                            event('stock',msg)
                        if changes:
                            prefix='【Pro 测试】' if variant.get('test') else ''
                            if STATE['notifications']:
                                notify(prefix+'检测到可自提库存，请到 Apple 官网确认：\n'+variant.get('model','iPhone Duo')+' '+variant['capacity']+' '+variant['colour']+'\n'+ '、'.join(r['store'] for r in changes))
                            if not variant.get('test'):
                                PENDING_PHONE.append(variant.get('model','iPhone Duo')+' '+variant['capacity']+' '+variant['colour']+' at '+', '.join(r['store'] for r in changes))
                    STATE['task']=None
                else:
                    return self.send(404,{'error':'Not found'})
                save()
            WAKE.set()
            self.send(200,{'ok':True})
        except (ValueError,KeyError,TypeError) as exc:
            self.send(400,{'error':str(exc)})

    def log_message(self,*args):
        pass

if __name__=='__main__':
    httpd=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
    # The normal Chrome session collects pages; isolated automated sessions
    # currently receive HTTP 541 from Apple. Tasks are leased via the local API.
    print('Duo Monitor: http://127.0.0.1:8765',flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
