"""Desktop OAuth with PKCE; tokens stay in process memory."""
import base64
import hashlib
import json
import secrets
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CONFIG = Path(__file__).resolve().parent.parent / 'data' / 'giftcard-oauth-client.json'
SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'


def validate_config(data):
    config = data.get('installed', {}) if isinstance(data, dict) else {}
    if not isinstance(config, dict) or not str(config.get('client_id', '')).endswith('.apps.googleusercontent.com') or not config.get('client_secret'):
        raise ValueError('请导入 Google Cloud 下载的“桌面应用”OAuth 客户端 JSON。')
    return {key: str(config[key]) for key in ('client_id', 'client_secret')}


def configuration():
    try:
        return validate_config(json.loads(CONFIG.read_text(encoding='utf-8-sig')))
    except (OSError, ValueError):
        raise ValueError('尚未配置 Google OAuth 客户端，请先导入桌面应用 JSON。') from None


def http_json(url, form=None, token=None):
    headers = {'Authorization': 'Bearer '+token} if token else {}
    data = urlencode(form).encode() if form is not None else None
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 401:
            raise ValueError('Google 登录已失效，请重新授权邮箱。') from None
        if exc.code == 403:
            raise ValueError('Google 拒绝访问：请启用 Gmail API、添加测试用户，并授予邮件只读权限。') from None
        if exc.code == 429:
            raise ValueError('Google 请求过于频繁，请稍后重试。') from None
        raise ValueError('Google 请求失败，请检查客户端配置或重新登录授权。') from None


class OAuth:
    def __init__(self):
        self.pending = None

    def begin(self, port, hint=''):
        config = configuration()
        verifier = secrets.token_urlsafe(48)
        state = secrets.token_urlsafe(32)
        redirect = f'http://127.0.0.1:{port}/oauth/callback'
        self.pending = dict(config=config, verifier=verifier, state=state, redirect=redirect, expires=time.monotonic()+600)
        params = dict(client_id=config['client_id'], redirect_uri=redirect, response_type='code',
                      scope=SCOPE, state=state, code_challenge_method='S256',
                      code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),
                      access_type='offline', prompt='select_account consent')
        if hint:
            params['login_hint'] = hint
        return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(params)

    def consume(self, params):
        pending = self.pending
        if not pending or not secrets.compare_digest(params.get('state', ''), pending['state']) or time.monotonic() > pending['expires']:
            raise ValueError('授权链接已过期或无效，请回到后台重新点击 Google 登录。')
        self.pending = None
        if params.get('error'):
            raise ValueError('Google 授权已取消，原有邮箱连接保持不变。')
        if not params.get('code'):
            raise ValueError('Google 未返回授权码，请重新登录。')
        return pending

    def finish(self, params, pending):
        tokens = http_json('https://oauth2.googleapis.com/token', dict(
            **pending['config'], code=params['code'], code_verifier=pending['verifier'],
            redirect_uri=pending['redirect'], grant_type='authorization_code'))
        if SCOPE not in tokens.get('scope', '').split():
            raise ValueError('未获得 Gmail 只读权限，请重新授权并勾选邮件读取权限。')
        client = Gmail(tokens, pending['config'])
        profile = client.get('profile')
        return client, profile['emailAddress']


class Gmail:
    def __init__(self, tokens, config):
        self.tokens = tokens
        self.config = config
        self.expires = time.monotonic()+int(tokens.get('expires_in', 3600))-60

    def get(self, resource, **params):
        if time.monotonic() >= self.expires:
            if not self.tokens.get('refresh_token'):
                raise ValueError('Google 登录已过期，请重新授权。')
            refreshed = http_json('https://oauth2.googleapis.com/token', dict(
                **self.config, refresh_token=self.tokens['refresh_token'], grant_type='refresh_token'))
            self.tokens.update(refreshed)
            self.expires = time.monotonic()+int(refreshed.get('expires_in', 3600))-60
        url = 'https://gmail.googleapis.com/gmail/v1/users/me/' + resource
        if params:
            url += '?' + urlencode(params)
        return http_json(url, token=self.tokens['access_token'])

    def search(self, query):
        ids, page = [], None
        while True:
            params = dict(q=query, maxResults=500, includeSpamTrash='false')
            if page:
                params['pageToken'] = page
            response = self.get('messages', **params)
            ids.extend(item['id'] for item in response.get('messages', []))
            page = response.get('nextPageToken')
            if not page:
                return list(dict.fromkeys(ids))

    def read(self, message_id):
        if not message_id.isalnum():
            raise ValueError('邮件 ID 无效。')
        meta = self.get('messages/'+message_id, format='minimal')
        if meta.get('sizeEstimate', 0) > 12*1024*1024:
            raise ValueError('邮件超过 12 MB，请人工核对。')
        message = self.get('messages/'+message_id, format='raw')
        raw = message.get('raw')
        if not raw:
            raise ValueError('邮件正文不可用。')
        return base64.urlsafe_b64decode(raw + '='*((-len(raw)) % 4))

    def logout(self):
        self.tokens.clear()
