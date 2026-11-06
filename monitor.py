"""Apple Store pickup checks through the public product page."""
import math
import re

BASE = 'https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-'
VARIANTS = [dict(id=f'{capacity}-{colour}', capacity=capacity.upper(), colour=label,
                 url=BASE+capacity+'-'+colour+'-unlocked')
            for colour, label in [('night-sky', 'Night Sky'), ('star-white', 'Star White')]
            for capacity in ['256gb', '512gb', '1tb', '2tb']]
STORES = {}  # US stores are discovered from each ZIP query.


for variant in VARIANTS:
    variant['model'] = 'iPhone Duo'
PRO_VARIANTS = [dict(id='pro-256gb-black', model='iPhone 18 Pro', capacity='256GB',
                     colour='Black', test=True,
                     url='https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.3-inch-display-256gb-black-unlocked')]
MODELS = {'duo': 'iPhone Duo', 'pro-test': 'iPhone 18 Pro（真实库存测试）'}

def variants_for(model):
    return PRO_VARIANTS if model == 'pro-test' else VARIANTS

def classify(disabled, message):
    text = message.lower()
    if re.search(r'currently unavailable|unavailable for pickup|not available(?: today)?', text):
        return 'unavailable'
    if not disabled and re.match(r'available\b', text.strip()):
        return 'available'
    return 'unknown'

def stock_changes(previous, current):
    old = {r['store_id']:r['status'] for r in previous}
    return [r for r in current if r['status']=='available' and old.get(r['store_id'])!='available']


# A server-enforced monitoring boundary, not a display preference.
MAX_DISTANCE_KM = 50
SCOPE_VERSION = 3

def valid_distance(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0

def within_monitoring_scope(row):
    value = row.get('distance_km')
    return valid_distance(value) and value <= MAX_DISTANCE_KM

def migrate_monitoring_scope(state):
    """Remove legacy out-of-radius results without generating stock alerts."""
    for result in state.get('results', {}).values():
        rows = result.get('stores', [])
        result['stores'] = [row for row in rows if within_monitoring_scope(row)]
        if any(not valid_distance(row.get('distance_km')) for row in rows):
            result['error'] = '旧库存距离未确认，请使用扩展 1.4.2 重新采集'
    if state.get('scope_version') != SCOPE_VERSION:
        # Old stock notices may refer to stores that are no longer monitored.
        state['events'] = [event for event in state.get('events', []) if event.get('kind') != 'stock']
    state['scope_version'] = SCOPE_VERSION
    state['max_distance_km'] = MAX_DISTANCE_KM
