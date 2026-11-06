"""Apple Store pickup checks through the public product page."""
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

