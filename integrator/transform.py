import hashlib
import json
import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

VAT_RATE = Decimal('1.21')
DEFAULT_COLOR = 'N/A'


def _sum_stocks(stocks):
    if not isinstance(stocks, dict):
        return 0
    return sum(int(v) for v in stocks.values() if isinstance(v, (int, float)))


def _apply_vat(price):
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    value = (Decimal(str(price)) * VAT_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return float(value)


def _color(attributes):
    if isinstance(attributes, dict):
        color = attributes.get('color')
        if isinstance(color, str) and color.strip():
            return color
    return DEFAULT_COLOR


def transform_product(raw):
    sku = raw.get('id')
    if not sku:
        return None
    price = _apply_vat(raw.get('price_vat_excl'))
    if price is None:
        logger.warning('skipping sku=%s: invalid price=%r', sku, raw.get('price_vat_excl'))
        return None
    return {
        'sku': sku,
        'title': raw.get('title', ''),
        'price': price,
        'stock': _sum_stocks(raw.get('stocks')),
        'color': _color(raw.get('attributes')),
    }


def transform_products(raw_list):
    """Transform raw ERP records, drop invalid ones, deduplicate by SKU.

    When the same SKU appears multiple times, the last occurrence wins. That
    matches how most ERP exports emit "latest state" snapshots.
    """
    latest = {}
    for raw in raw_list:
        product = transform_product(raw)
        if product is None:
            continue
        latest[product['sku']] = product
    return list(latest.values())


def compute_hash(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
    ).hexdigest()
