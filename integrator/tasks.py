import json
import logging
from pathlib import Path

from celery import shared_task
from django.conf import settings

from .client import EshopClient
from .models import Product
from .transform import compute_hash, transform_products

logger = logging.getLogger(__name__)


@shared_task(name='integrator.sync_products')
def sync_products(data_path=None):
    path = Path(data_path or settings.ERP_DATA_PATH)
    with path.open(encoding='utf-8') as f:
        raw = json.load(f)

    products = transform_products(raw)
    client = EshopClient()
    stats = {'created': 0, 'updated': 0, 'unchanged': 0}

    for product in products:
        payload_hash = compute_hash(product)
        record, _ = Product.objects.get_or_create(sku=product['sku'])

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
        record.save()

    logger.info('sync finished: %s', stats)
    return stats
