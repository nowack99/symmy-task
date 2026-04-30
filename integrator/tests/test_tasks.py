import json

import pytest
import responses

from integrator.models import Product
from integrator.tasks import sync_products


BASE_URL = 'https://api.test.local/v1'

SAMPLE = [
    {"id": "SKU-A", "title": "Alpha", "price_vat_excl": 100,
     "stocks": {"praha": 3}, "attributes": {"color": "red"}},
    {"id": "SKU-B", "title": "Beta", "price_vat_excl": 200,
     "stocks": {"praha": 1}, "attributes": {}},
]


@pytest.fixture
def erp_file(tmp_path, settings):
    path = tmp_path / 'erp.json'
    path.write_text(json.dumps(SAMPLE))
    settings.ESHOP_BASE_URL = BASE_URL
    settings.ESHOP_API_KEY = 'test-key'
    settings.ESHOP_RATE_LIMIT = 10
    settings.ERP_DATA_PATH = str(path)
    return path


@responses.activate
@pytest.mark.django_db
def test_first_sync_creates_all_products(erp_file):
    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)
    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)

    stats = sync_products()

    assert stats['created'] == 2
    assert stats['updated'] == 0
    assert stats['unchanged'] == 0
    assert Product.objects.count() == 2
    assert all(p.remote_exists for p in Product.objects.all())


@responses.activate
@pytest.mark.django_db
def test_second_sync_skips_unchanged(erp_file):
    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)
    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)
    sync_products()
    responses.reset()

    stats = sync_products()

    assert stats['unchanged'] == 2
    assert stats['created'] == 0
    assert stats['updated'] == 0
    assert len(responses.calls) == 0


@responses.activate
@pytest.mark.django_db
def test_changed_product_triggers_patch(erp_file):
    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)
    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)
    sync_products()
    responses.reset()

    modified = json.loads(erp_file.read_text())
    modified[0]['price_vat_excl'] = 999
    erp_file.write_text(json.dumps(modified))

    responses.add(responses.PATCH, f'{BASE_URL}/products/SKU-A/', json={}, status=200)

    stats = sync_products()

    assert stats['updated'] == 1
    assert stats['unchanged'] == 1
    assert len(responses.calls) == 1
    assert responses.calls[0].request.method == 'PATCH'


@responses.activate
@pytest.mark.django_db
def test_sync_uses_transformed_payload(erp_file):
    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)
    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)

    sync_products()

    sent = [json.loads(call.request.body) for call in responses.calls]
    sku_a = next(p for p in sent if p['sku'] == 'SKU-A')
    assert sku_a['price'] == 121.0  # 100 * 1.21
    assert sku_a['stock'] == 3
    assert sku_a['color'] == 'red'


@pytest.mark.django_db
def test_non_list_input_raises(tmp_path, settings):
    path = tmp_path / 'erp.json'
    path.write_text(json.dumps({"not": "a list"}))
    settings.ERP_DATA_PATH = str(path)
    with pytest.raises(ValueError, match='expected a list'):
        sync_products()


@responses.activate
@pytest.mark.django_db
def test_invalid_count_is_reported(tmp_path, settings):
    bad = [
        {"id": "SKU-A", "title": "OK", "price_vat_excl": 100,
         "stocks": {"a": 1}, "attributes": {}},
        {"id": "SKU-B", "title": "negative price", "price_vat_excl": -50,
         "stocks": {}, "attributes": {}},
        {"id": "SKU-C", "title": "null price", "price_vat_excl": None,
         "stocks": {}, "attributes": {}},
    ]
    path = tmp_path / 'erp.json'
    path.write_text(json.dumps(bad))
    settings.ESHOP_BASE_URL = BASE_URL
    settings.ESHOP_API_KEY = 'k'
    settings.ESHOP_RATE_LIMIT = 10
    settings.ERP_DATA_PATH = str(path)

    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)
    stats = sync_products()
    assert stats['created'] == 1
    assert stats['invalid'] == 2


@responses.activate
@pytest.mark.django_db
def test_invalid_records_are_logged_with_sample(tmp_path, settings, caplog):
    import logging
    bad = [
        {"id": "SKU-A", "price_vat_excl": 100, "stocks": {}, "attributes": {}},
        {"id": "SKU-B", "price_vat_excl": -1, "stocks": {}, "attributes": {}},
        "not a dict at all",
    ]
    path = tmp_path / 'erp.json'
    path.write_text(json.dumps(bad))
    settings.ESHOP_BASE_URL = BASE_URL
    settings.ESHOP_API_KEY = 'k'
    settings.ESHOP_RATE_LIMIT = 10
    settings.ERP_DATA_PATH = str(path)

    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)
    with caplog.at_level(logging.WARNING, logger='integrator.tasks'):
        sync_products()

    warnings = [r for r in caplog.records if r.levelname == 'WARNING']
    assert any('dropped 2 invalid records' in r.message for r in warnings)
    assert any("'not a dict at all'" in r.message or 'not a dict at all' in r.message for r in warnings)


@responses.activate
@pytest.mark.django_db
def test_high_invalid_ratio_logs_critical(tmp_path, settings, caplog):
    import logging
    bad = [
        {"id": "SKU-A", "price_vat_excl": 100, "stocks": {}, "attributes": {}},
        {"id": "SKU-B", "price_vat_excl": -1, "stocks": {}, "attributes": {}},
        {"id": "SKU-C", "price_vat_excl": None, "stocks": {}, "attributes": {}},
    ]
    path = tmp_path / 'erp.json'
    path.write_text(json.dumps(bad))
    settings.ESHOP_BASE_URL = BASE_URL
    settings.ESHOP_API_KEY = 'k'
    settings.ESHOP_RATE_LIMIT = 10
    settings.ERP_DATA_PATH = str(path)

    responses.add(responses.POST, f'{BASE_URL}/products/', json={}, status=201)
    with caplog.at_level(logging.CRITICAL, logger='integrator.tasks'):
        sync_products()

    assert any('exceeds 10% threshold' in r.message for r in caplog.records)
