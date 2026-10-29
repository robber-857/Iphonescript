"""Apple Store pickup checks through the public product page."""
import re

BASE = 'https://www.apple.com/au/shop/buy-iphone/iphone-duo/7.6-inch-display-'
VARIANTS = [dict(id=f'{capacity}-{colour}', capacity=capacity.upper(), colour=label,
                 url=BASE+capacity+'-'+colour)
            for colour, label in [('night-sky', 'Night Sky'), ('star-white', 'Star White')]
            for capacity in ['256gb', '512gb', '1tb', '2tb']]
STORES = {'R238': 'Apple Sydney', 'R523': 'Apple Broadway', 'R254': 'Apple Bondi',
          'R253': 'Apple Chatswood Chase', 'R606': 'Apple Miranda',
          'R344': 'Apple Castle Towers', 'R440': 'Apple Penrith'}

for variant in VARIANTS:
    variant['model'] = 'iPhone Duo'
PRO_VARIANTS = [dict(id='pro-256gb-black', model='iPhone 18 Pro', capacity='256GB',
                     colour='Black', test=True,
                     url='https://www.apple.com/au/shop/buy-iphone/iphone-18-pro/6.3-inch-display-256gb-black')]
MODELS = {'duo': 'iPhone Duo', 'pro-test': 'iPhone 18 Pro（真实库存测试）'}

def variants_for(model):
    return PRO_VARIANTS if model == 'pro-test' else VARIANTS

def classify(disabled, message):
    text = message.lower()
    if 'currently unavailable' in text or 'unavailable for pickup' in text:
        return 'unavailable'
    if not disabled and re.search(r'available|pick.?up|today|tomorrow', text):
        return 'available'
    return 'unknown'

def stock_changes(previous, current):
    old = {r['store_id']:r['status'] for r in previous}
    return [r for r in current if r['status']=='available' and old.get(r['store_id'])!='available']
