"""Twilio outbound calls; credentials stay in local data/phone.json."""
import base64
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from xml.sax.saxutils import escape

class Phone:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.lock = threading.Lock()
        self.config = self.read('phone.json', {'enabled': False})
        self.usage = self.read('phone-usage.json', {})

    def read(self, name, default):
        try:
            return json.loads((self.directory / name).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return default

    def write(self, name, value):
        self.directory.mkdir(exist_ok=True)
        path = self.directory / name
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(value), encoding='utf-8')
        temp.replace(path)

    def status(self):
        with self.lock:
            number = self.config.get('to', '')
            return dict(enabled=self.config.get('enabled', False),
                        configured=all(self.config.get(k) for k in ('sid','token','from','to')),
                        destination=('••••' + number[-4:]) if number else '',
                        last=self.usage.get('last_status', '尚未拨号'))

    def configure(self, payload):
        with self.lock:
            cfg = dict(self.config)
            if not isinstance(payload.get('enabled'), bool):
                raise ValueError('电话提醒开关格式错误')
            for key in ('sid','token','from','to'):
                value = str(payload.get(key, '')).strip()
                if value:
                    cfg[key] = value
            cfg['enabled'] = payload['enabled']
            if cfg['enabled'] or any(payload.get(k) for k in ('sid','token','from','to')):
                if not re.fullmatch(r'AC[0-9a-fA-F]{32}', cfg.get('sid','')):
                    raise ValueError('Account SID 应为 AC 开头的 34 位字符')
                if not re.fullmatch(r'[0-9a-fA-F]{32}', cfg.get('token','')):
                    raise ValueError('请输入有效的 Auth Token')
                for key in ('from','to'):
                    if not re.fullmatch(r'\+[1-9][0-9]{7,14}', cfg.get(key,'')):
                        raise ValueError('电话号码请使用 +国家码 格式，例如 +614xxxxxxxx')
            self.write('phone.json', cfg)
            self.config = cfg

    def call(self, message, report, test=False):
        with self.lock:
            cfg = dict(self.config)
            if not test and not cfg.get('enabled'):
                return False
            if not all(cfg.get(k) for k in ('sid','token','from','to')):
                raise ValueError('请先保存完整 Twilio 配置')
            now = time.time()
            day = datetime.now(timezone.utc).date().isoformat()
            count = self.usage.get('count', 0) if self.usage.get('day') == day else 0
            if now - self.usage.get('last_attempt', 0) < 600:
                raise ValueError('电话提醒冷却中：两次拨号至少间隔 10 分钟')
            if count >= 3:
                raise ValueError('已达到每日最多 3 次拨号限制（UTC 日期，含测试）')
            self.usage.update(day=day,count=count+1,last_attempt=now,last_status='正在提交拨号请求')
            self.write('phone-usage.json', self.usage)

        def run():
            twiml = '<Response><Say language="en-AU">' + escape(message) + '</Say></Response>'
            body = urlencode({'To':cfg['to'],'From':cfg['from'],'Twiml':twiml,'Timeout':20,'TimeLimit':60}).encode()
            auth = base64.b64encode((cfg['sid']+':'+cfg['token']).encode()).decode()
            request = Request('https://api.twilio.com/2010-04-01/Accounts/'+cfg['sid']+'/Calls.json',
                              data=body,headers={'Authorization':'Basic '+auth,'Content-Type':'application/x-www-form-urlencoded'})
            try:
                with urlopen(request, timeout=20) as response:
                    result = json.load(response)
                status = 'Twilio 已接受拨号请求（不代表已接听），请在 Twilio 通话日志查看结果'
                if not result.get('sid'):
                    status = 'Twilio 返回异常，请检查通话日志；不会自动重拨'
            except HTTPError as exc:
                status = f'电话请求失败（HTTP {exc.code}），请检查 Twilio 号码、余额和拨号权限'
            except (URLError, OSError, ValueError):
                status = '电话请求结果不明，请查看 Twilio 通话日志；不会自动重拨'
            with self.lock:
                self.usage['last_status'] = status
                self.write('phone-usage.json', self.usage)
            report(status)
        threading.Thread(target=run, daemon=True).start()
        return True
