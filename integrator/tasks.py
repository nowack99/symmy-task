import json
import logging
from pathlib import Path

from celery import shared_task
from django.conf import settings

from .client import EshopClient
from .models import Product
from .transform import compute_hash, transform_product

logger = logging.getLogger(__name__)

INVALID_RATIO_THRESHOLD = 0.1
INVALID_LOG_SAMPLE_SIZE = 10


@shared_task(name='integrator.sync_products')
def sync_products(data_path=None):
    path = Path(data_path or settings.ERP_DATA_PATH)
    with path.open(encoding='utf-8') as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError(f'expected a list of products in {path}, got {type(raw).__name__}')

    products_by_sku = {}
    invalid_records = []
    for record in raw:
        transformed = transform_product(record) if isinstance(record, dict) else None
        if transformed is None:
            invalid_records.append(record)
            continue
        products_by_sku[transformed['sku']] = transformed

    if invalid_records:
        logger.warning(
            'dropped %d invalid records, sample: %s',
            len(invalid_records), invalid_records[:INVALID_LOG_SAMPLE_SIZE],
        )
        if len(invalid_records) / len(raw) >= INVALID_RATIO_THRESHOLD:
            logger.critical(
                'invalid-record ratio %.0f%% exceeds %.0f%% threshold - check ERP export',
                100 * len(invalid_records) / len(raw),
                100 * INVALID_RATIO_THRESHOLD,
            )

    products = list(products_by_sku.values())
    client = EshopClient()
    existing = Product.objects.in_bulk(list(products_by_sku.keys()))
    stats = {'created': 0, 'updated': 0, 'unchanged': 0, 'invalid': len(invalid_records)}

    for product in products:
        payload_hash = compute_hash(product)
        record = existing.get(product['sku'])
        is_new = record is None
        if is_new:
            record = Product(sku=product['sku'])

        if record.remote_exists and record.payload_hash == payload_hash:
            stats['unchanged'] += 1
            continue

        if record.remote_exists:
            client.update_product(product['sku'], product)
            stats['updated'] += 1
        else:
            client.create_product(product)
            stats['created'] += 1

        record.payload_hash = payload_hash
        record.remote_exists = True
        record.save(force_insert=is_new)

    logger.info('sync finished: %s', stats)
    return stats
