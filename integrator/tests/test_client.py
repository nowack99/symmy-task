import time

import pytest
import responses

from integrator.client import EshopClient


BASE_URL = 'https://api.test.local/v1'


@pytest.fixture
def client():
    return EshopClient(base_url=BASE_URL, api_key='test-key', rate_limit=5, max_retries=3)


@responses.activate
def test_auth_header_is_attached(client):
    responses.add(responses.POST, f'{BASE_URL}/products/', json={'ok': True}, status=201)
    client.create_product({'sku': 'X'})
    assert responses.calls[0].request.headers['X-Api-Key'] == 'test-key'


@responses.activate
def test_create_uses_post_to_products(client):
    responses.add(responses.POST, f'{BASE_URL}/products/', json={'ok': True}, status=201)
    client.create_product({'sku': 'A', 'price': 100})
    call = responses.calls[0]
    assert call.request.method == 'POST'
    assert call.request.url == f'{BASE_URL}/products/'


@responses.activate
def test_update_uses_patch_with_sku_in_path(client):
    responses.add(responses.PATCH, f'{BASE_URL}/products/SKU-A/', json={'ok': True}, status=200)
    client.update_product('SKU-A', {'price': 99})
    call = responses.calls[0]
    assert call.request.method == 'PATCH'
    assert call.request.url == f'{BASE_URL}/products/SKU-A/'


@responses.activate
def test_retries_on_429_until_success(client):
    url = f'{BASE_URL}/products/'
    responses.add(responses.POST, url, status=429, headers={'Retry-After': '0'})
    responses.add(responses.POST, url, status=429, headers={'Retry-After': '0'})
    responses.add(responses.POST, url, json={'ok': True}, status=201)
    client.create_product({'sku': 'R'})
    assert len(responses.calls) == 3


def test_retry_adapter_is_configured_for_429(client):
    adapter = client._session.get_adapter(f'{BASE_URL}/products/')
    retry = adapter.max_retries
    assert 429 in retry.status_forcelist
    assert retry.respect_retry_after_header is True


@responses.activate
def test_rate_limit_blocks_before_exceeding_window():
    client = EshopClient(base_url=BASE_URL, api_key='k', rate_limit=2, max_retries=0)
    url = f'{BASE_URL}/products/'
    for _ in range(5):
        responses.add(responses.POST, url, json={'ok': True}, status=201)
    start = time.monotonic()
    for i in range(5):
        client.create_product({'sku': f'X{i}'})
    elapsed = time.monotonic() - start
    # 5 requests at 2/s should take at least ~2s
    assert elapsed >= 1.5
    assert len(responses.calls) == 5
