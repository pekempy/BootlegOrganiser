import time
import requests

def handle_rate_limit(response):
    """
    Checks if a response indicates a rate limit has been reached and waits if necessary.
    Returns True if a wait occurred, False otherwise.
    """
    # Check status code or X-RateLimit-Remaining header
    is_rate_limited = (response.status_code == 429 or 
                       response.headers.get('X-RateLimit-Remaining') == '0')
    
    if is_rate_limited:
        # 1. Try Retry-After (usually in seconds)
        wait_time = response.headers.get('Retry-After')
        if wait_time:
            try:
                wait_time = int(wait_time)
            except ValueError:
                wait_time = 60 # Fallback
        else:
            # 2. Try X-RateLimit-Reset (epoch time)
            reset_time = response.headers.get('X-RateLimit-Reset')
            if reset_time:
                try:
                    wait_time = max(0, int(reset_time) - int(time.time()))
                except ValueError:
                    wait_time = 60 # Fallback
            else:
                # 3. Default fallback
                wait_time = 60
        
        # Ensure we don't wait forever, but respect the limit
        wait_time = min(max(wait_time, 1), 3600) 
        
        print(f"\n[Rate Limit] Limit reached. Waiting for {wait_time} seconds before retrying...")
        time.sleep(wait_time + 1) # Plus a small buffer
        return True
    
    return False

def authenticated_request(method, url, session=None, **kwargs):
    """
    Performs an authenticated request with automatic rate limit handling and retries.
    """
    if session is None:
        session = requests.Session()
    
    # Use the session if provided, otherwise requests.request
    req_func = getattr(session, method.lower())
    
    retries = kwargs.pop('retries', 3)
    
    while retries >= 0:
        try:
            response = req_func(url, **kwargs)
            
            if handle_rate_limit(response):
                # Rate limit was handled, retry the same request if we have retries left
                if retries > 0:
                    continue 
            
            # If we still get a 429 after waiting, or any other error, raise_for_status might catch it
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            if retries == 0:
                raise e
            print(f"\n[API Error] {e}. Retrying ({retries} left)...")
            time.sleep(2)
            retries -= 1
    
    return None
