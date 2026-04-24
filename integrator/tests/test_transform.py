from integrator.transform import compute_hash, transform_product, transform_products


ERP_SAMPLE = [
    {"id": "SKU-001", "title": "Kávovar Espresso", "price_vat_excl": 12400.5,
     "stocks": {"praha": 5, "brno": 3}, "attributes": {"color": "stříbrná"}},
    {"id": "SKU-002", "title": "Sleva - chyba", "price_vat_excl": -150.0,
     "stocks": {"praha": 10}, "attributes": {}},
    {"id": "SKU-003", "title": "Mlýnek", "price_vat_excl": 1500,
     "stocks": {"externi": 50}, "attributes": None},
    {"id": "SKU-004", "title": "Hrnek", "price_vat_excl": None,
     "stocks": {"praha": 10}, "attributes": {"color": "černá"}},
    {"id": "SKU-006", "title": "Tablety", "price_vat_excl": 250,
     "stocks": {"praha": 100}, "attributes": {}},
    {"id": "SKU-006", "title": "Tablety", "price_vat_excl": 250,
     "stocks": {"praha": 100}, "attributes": {}},
    {"id": "SKU-008", "title": "Filtry", "price_vat_excl": 300,
     "stocks": {"praha": "N/A"}, "attributes": {"color": "bílá"}},
]


def _by_sku(products):
    return {p['sku']: p for p in products}


def test_vat_is_applied_and_rounded_half_up():
    result = _by_sku(transform_products(ERP_SAMPLE))
    # 12400.5 * 1.21 = 15004.605 -> 15004.61
    assert result['SKU-001']['price'] == 15004.61
    assert result['SKU-003']['price'] == 1815.0
    assert result['SKU-008']['price'] == 363.0


def test_stocks_are_summed_across_warehouses():
    result = _by_sku(transform_products(ERP_SAMPLE))
    assert result['SKU-001']['stock'] == 8  # 5 + 3
    assert result['SKU-003']['stock'] == 50


def test_non_numeric_stock_values_are_ignored():
    result = _by_sku(transform_products(ERP_SAMPLE))
    assert result['SKU-008']['stock'] == 0  # "N/A" dropped


def test_invalid_prices_are_dropped():
    result = _by_sku(transform_products(ERP_SAMPLE))
    assert 'SKU-002' not in result  # negative
    assert 'SKU-004' not in result  # null


def test_missing_color_falls_back_to_default():
    result = _by_sku(transform_products(ERP_SAMPLE))
    assert result['SKU-001']['color'] == 'stříbrná'
    assert result['SKU-003']['color'] == 'N/A'  # attributes: null
    assert result['SKU-006']['color'] == 'N/A'  # attributes: {}
    assert result['SKU-008']['color'] == 'bílá'


def test_duplicate_skus_are_deduplicated():
    result = transform_products(ERP_SAMPLE)
    skus = [p['sku'] for p in result]
    assert skus.count('SKU-006') == 1


def test_last_occurrence_wins_on_duplicate():
    raw = [
        {"id": "X", "price_vat_excl": 100, "stocks": {"a": 1}, "attributes": {}},
        {"id": "X", "price_vat_excl": 200, "stocks": {"a": 9}, "attributes": {}},
    ]
    result = transform_products(raw)
    assert len(result) == 1
    assert result[0]['price'] == 242.0  # 200 * 1.21


def test_missing_sku_is_skipped():
    assert transform_product({"price_vat_excl": 100}) is None


def test_hash_is_stable_for_same_payload():
    a = {'sku': 'X', 'price': 100.0, 'stock': 5, 'color': 'red', 'title': 'A'}
    b = {'title': 'A', 'color': 'red', 'stock': 5, 'price': 100.0, 'sku': 'X'}
    assert compute_hash(a) == compute_hash(b)


def test_hash_changes_when_payload_changes():
    base = {'sku': 'X', 'price': 100.0, 'stock': 5, 'color': 'red', 'title': 'A'}
    changed = dict(base, price=101.0)
    assert compute_hash(base) != compute_hash(changed)
