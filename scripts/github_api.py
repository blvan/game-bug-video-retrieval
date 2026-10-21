"""Small cached GitHub REST client; all persisted responses are public API data."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import re

API_ROOT = 'https://api.github.com'
NEXT_PATTERN = re.compile(r'<([^>]+)>;\s*rel="next"')


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


class CollectionPaused(RuntimeError):
    """A retryable stop; completed work must be exported and kept."""


class GitHubClient:
    def __init__(self, token=None, cache_dir=None, max_wait=60, request_budget=0,
                 refresh_cache=False, search_interval=None):
        self.headers = {'Accept': 'application/vnd.github+json',
                        'User-Agent': 'game-bug-video-retrieval/0.2',
                        'X-GitHub-Api-Version': '2022-11-28'}
        if token:
            self.headers['Authorization'] = f'Bearer {token}'
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_wait = max_wait
        self.request_budget = request_budget
        self.refresh_cache = refresh_cache
        self.search_interval = search_interval if search_interval is not None else (2.1 if token else 6.1)
        self.last_search = 0.0
        self.requests = self.cache_hits = 0
        self.incomplete_searches = []
        self.capped_searches = []
        self.rate_limits = {}

    def get(self, path, params=None):
        url = path if path.startswith('https://') else API_ROOT + path
        if params:
            url += '?' + urlencode(params)
        if urlparse(url).hostname != 'api.github.com':
            raise ValueError('Refusing credentials outside api.github.com')
        cache = self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.json') if self.cache_dir else None
        if cache and cache.exists() and not self.refresh_cache:
            self.cache_hits += 1
            return json.loads(cache.read_text(encoding='utf-8'))
        for attempt in range(3):
            if self.request_budget and self.requests >= self.request_budget:
                raise CollectionPaused('API request budget reached; rerun the same command to resume')
            if '/search/' in url:
                time.sleep(max(0, self.search_interval - (time.monotonic() - self.last_search)))
                self.last_search = time.monotonic()
            self.requests += 1
            try:
                with urlopen(Request(url, headers=self.headers), timeout=30) as response:
                    data = json.load(response)
                    resource = response.headers.get('X-RateLimit-Resource', 'core')
                    self.rate_limits[resource] = {k: response.headers.get('X-RateLimit-' + k) for k in ('Remaining', 'Reset')}
                    result = {'data': data, 'link': response.headers.get('Link', ''),
                              'fetched_at': time.time(), 'url': url}
                    if cache:
                        atomic_json(cache, result)
                    return result
            except HTTPError as error:
                if error.code in (403, 429):
                    # A plain 403 is a permissions error, not necessarily a rate limit.
                    message = error.read().decode('utf-8', errors='replace')
                    if error.code == 403 and not (error.headers.get('Retry-After') or error.headers.get('X-RateLimit-Remaining') == '0' or 'rate limit' in message.lower()):
                        raise
                    retry_after = error.headers.get('Retry-After')
                    reset = error.headers.get('X-RateLimit-Reset')
                    try:
                        delay = float(retry_after) if retry_after else max(1, float(reset) - time.time() + 1) if reset else 60 * (attempt + 1)
                    except (TypeError, ValueError):
                        delay = 60 * (attempt + 1)
                    if delay > self.max_wait or attempt == 2:
                        raise CollectionPaused(f'GitHub rate limit; retry after about {delay:.0f}s (checkpoint saved)') from error
                    logging.warning('GitHub rate limit: waiting %.0fs', delay)
                    # Short sleeps keep Ctrl-C responsive.
                    end = time.monotonic() + delay
                    while time.monotonic() < end:
                        time.sleep(min(1, end - time.monotonic()))
                    continue
                if error.code < 500:
                    raise
                if attempt == 2:
                    raise CollectionPaused(f'GitHub HTTP {error.code}; resume later') from error
            except (URLError, TimeoutError) as error:
                if attempt == 2:
                    raise CollectionPaused('GitHub network failure; resume later') from error
            time.sleep(2 ** attempt)
        raise AssertionError('unreachable')

    def pages(self, path, params=None):
        url = path
        while url:
            result = self.get(url, params)
            params = None
            data = result['data']
            if isinstance(data, dict) and 'items' in data:
                if data.get('incomplete_results'):
                    self.incomplete_searches.append(result['url'])
                    logging.warning('Incomplete GitHub search: %s', result['url'])
                if data.get('total_count', 0) > 1000 and result['url'] not in self.capped_searches:
                    self.capped_searches.append(result['url'])
                data = data['items']
            if not isinstance(data, list):
                raise ValueError(f'Expected list/items from {url}')
            yield data
            match = NEXT_PATTERN.search(result['link'])
            url = match.group(1) if match else None
