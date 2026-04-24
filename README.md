# Symmy Tasker

Sync z ERP exportu do fiktivního e-shop API. Jede jako Celery task, volání
API v testech mockuju přes `responses`.

## Spuštění

```sh
docker-compose up --build
```

Pustí Postgres, Redis, Django na `:8000` a Celery worker. Migrace naběhnou
samy.

Sync se vyvolá management commandem:

```sh
docker-compose exec web python manage.py sync_now           # inline
docker-compose exec web python manage.py sync_now --async   # přes Celery
```

Testy jedou na SQLite v paměti, takže Postgres k nim není potřeba:

```sh
docker-compose exec web pytest
# nebo lokálně bez Dockeru:
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pytest
```

## Co se tam děje

```
erp_data.json → transform → delta (hash) → EshopClient → API
                                 │
                                 └── Product model
```

Task načte JSON, prožene transformací, spočítá hash payloadu a porovná ho
s tím, co si pamatuje z minula. Stejný hash, skip. Jiný hash, pošle POST
(nový SKU) nebo PATCH (existuje).

Transformace sečte sklady ze všech warehousů, připočte 21 % DPH (přes
`Decimal`, float by občas vyplivl třeba `15004.609999…`) a nastaví výchozí
barvu `"N/A"`. Záznamy s nevalidní cenou (záporná, null) zahazuju a logguju
warning. Nechci aby kvůli jednomu blbému řádku uvízl celý sync. Duplikáty
SKU řeším tak, že poslední vyhrává (ve vzorku je `SKU-006` dvakrát).

Rate limit (5 req/s) dělám ručně přes deque s timestampy, knihovna to
preventivně neumí. Retry na 429 nechávám na `urllib3.Retry`, tu umí
`Retry-After` nativně.

## Pár voleb

**Hash, ne timestamp.** Vzorek ERP `updated_at` neposílá a hash navíc chytne
i případ, kdy ERP pošle "update" beze změny.

**Rate limiter v paměti.** Pro jednoho workera v pohodě. Při víc workerech
bych to přepsal na Redis.

## Co jsem neřešil

Idempotence když worker spadne mezi POSTem a uložením hashe. Dá se to
vyřešit tak, že si hash uložím s `remote_exists=False` ještě před API
callem. Pro interview task mi to ale přišlo jako overkill. To samé metriky
a Celery Beat.

## Struktura

```
integrator/
  tasks.py                   # Celery task
  transform.py               # VAT, dedup, stocks, hash
  client.py                  # EshopClient
  models.py                  # Product (delta state)
  management/commands/sync_now.py
  tests/
core/
  settings.py
  settings_test.py           # sqlite :memory:
  celery.py
```
