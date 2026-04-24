import time
from collections import deque

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REQUEST_TIMEOUT = 10


class EshopClient:
    # In-process sliding 1-second window. Fine for one Celery worker;
    # scaling horizontally would want a Redis token bucket.

    def __init__(self, base_url=None, api_key=None, rate_limit=None, max_retries=3):
        self.base_url = (base_url or settings.ESHOP_BASE_URL).rstrip('/')
        self.rate_limit = rate_limit or settings.ESHOP_RATE_LIMIT
        self._window = deque()
        self._session = requests.Session()
        self._session.headers.update({'X-Api-Key': api_key or settings.ESHOP_API_KEY})

        retry = Retry(
            total=max_retries,
            status_forcelist=[429],
            allowed_methods=['POST', 'PATCH'],
            respect_retry_after_header=True,
            backoff_factor=0.5,
        )
        self._session.mount('https://', HTTPAdapter(max_retries=retry))
        self._session.mount('http://', HTTPAdapter(max_retries=retry))

    def create_product(self, payload):
        return self._request('POST', '/products/', json=payload)

    def update_product(self, sku, payload):
        return self._request('PATCH', f'/products/{sku}/', json=payload)

    def _throttle(self):
        now = time.monotonic()
        while self._window and now - self._window[0] >= 1.0:
            self._window.popleft()
        if len(self._window) >= self.rate_limit:
            time.sleep(1.0 - (now - self._window[0]))

    def _request(self, method, path, json=None):
        self._throttle()
        self._window.append(time.monotonic())
        response = self._session.request(
            method, f'{self.base_url}{path}', json=json, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json() if response.content else {}
