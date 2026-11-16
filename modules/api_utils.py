import logging
import time
import requests

from modules.config import config

logger = logging.getLogger(__name__)


def build_api_session(extra_headers: dict | None = None) -> requests.Session:
    """Create a requests.Session using the current config.api_key dynamically."""
    session = requests.Session()
    headers = {
        'User-Agent': 'BootOrganiser',
    }
    api_key = config.api_key
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    if extra_headers:
        headers.update(extra_headers)
    session.headers.update(headers)
    return session


def handle_rate_limit(response) -> bool:
    """
    Check if a response indicates a rate limit has been reached and wait if needed.
    Returns True if a wait occurred, False otherwise.
    """
    is_rate_limited = (
        response.status_code == 429
        or response.headers.get('X-RateLimit-Remaining') == '0'
    )

    if not is_rate_limited:
        return False

    wait_time = response.headers.get('Retry-After')
    if wait_time:
        try:
            wait_time = int(wait_time)
        except ValueError:
            wait_time = 60
    else:
        reset_time = response.headers.get('X-RateLimit-Reset')
        if reset_time:
            try:
                wait_time = max(0, int(reset_time) - int(time.time()))
            except ValueError:
                wait_time = 60
        else:
            wait_time = 60

    wait_time = min(max(wait_time, 1), 3600)
    logger.warning(f"Rate limit reached; waiting {wait_time}s before retrying")
    print(f"\n[Rate Limit] Limit reached. Waiting for {wait_time} seconds before retrying...")
    time.sleep(wait_time + 1)
    return True


def authenticated_request(method: str, url: str, session=None, **kwargs):
    """
    Perform an authenticated HTTP request with rate-limit handling and exponential
    backoff for transient 5xx / network errors.
    """
    owns_session = session is None
    if owns_session:
        session = build_api_session()

    req_func = getattr(session, method.lower())
    retries = kwargs.pop('retries', 3)
    kwargs.setdefault('timeout', 30)

    attempt = 0
    try:
        while True:
            try:
                response = req_func(url, **kwargs)

                if handle_rate_limit(response) and attempt < retries:
                    attempt += 1
                    continue

                # Retry transient 5xx errors with backoff
                if 500 <= response.status_code < 600 and attempt < retries:
                    attempt += 1
                    delay = min(2 ** attempt, 16)
                    logger.warning(f"Transient HTTP {response.status_code} for {url}; retrying in {delay}s")
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                if attempt >= retries:
                    raise e
                attempt += 1
                delay = min(2 ** attempt, 16)
                logger.warning(f"API request error on {url}: {e}; retrying in {delay}s")
                print(f"\n[API Error] {e}. Retrying ({retries - attempt + 1} left)...")
                time.sleep(delay)
    finally:
        if owns_session:
            session.close()
