from olclient2.openlibrary import OpenLibrary
from ..models.cache import OpenLibraryCache
import json
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class CachedOpenLibrary(OpenLibrary):
    """OpenLibrary client with caching support"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_work_class = self._create_cached_work()

    def _make_request(self, url, method='get', **kwargs):
        """Make a request with caching support"""
        # Try to get cached response for GET requests
        if method.lower() == 'get':
            cached_response = OpenLibraryCache.get_cached_response(url)
            if cached_response:
                logger.debug(f"Cache hit for {url}")
                return type('Response', (), {
                    'json': lambda: cached_response,
                    'raise_for_status': lambda: None,
                    'status_code': 200,
                    'text': json.dumps(cached_response)
                })
        
        # Make the actual request
        try:
            response = getattr(self.session, method.lower())(url, **kwargs)
            response.raise_for_status()
            
            # Cache successful GET responses
            if method.lower() == 'get' and response.status_code == 200:
                try:
                    response_data = response.json()
                    OpenLibraryCache.cache_response(url, response_data)
                    logger.debug(f"Cached response for {url}")
                except Exception as e:
                    logger.warning(f"Failed to cache response for {url}: {e}")
            
            return response
        except Exception as e:
            # If request fails, try to return cached version if available
            if method.lower() == 'get':
                cached_response = OpenLibraryCache.get_cached_response(url)
                if cached_response:
                    logger.info(f"Request failed, using cached response for {url}")
                    return type('Response', (), {
                        'json': lambda: cached_response,
                        'raise_for_status': lambda: None,
                        'status_code': 200,
                        'text': json.dumps(cached_response)
                    })
            raise

    def _create_cached_work(self):
        """Create a cached version of the Work class"""
        original_work = super().Work
        ol_instance = self
        
        class CachedWork(original_work):
            @classmethod
            def search(cls, **kwargs):
                # Construct the search URL exactly as the parent class would
                params = {k: v for k, v in kwargs.items() if v is not None}
                url = f"{ol_instance.base_url}/search.json?{urlencode(params)}"
                
                logger.debug(f"Making cached search request to {url}")
                try:
                    response = ol_instance._make_request(url)
                    data = response.json()
                    logger.info("Raw OpenLibrary response: num_found=%s, docs=%s", 
                              data.get('num_found'), len(data.get('docs', [])))
                    if not data.get('docs'):
                        return []
                    
                    # Process results and restructure to match expected format
                    if kwargs.get('limit', 1) > 1:
                        works = []
                        for doc in data['docs'][:kwargs.get('limit')]:
                            work = cls(doc['key'].split('/')[-1])
                            work.title = doc['title']
                            work.publish_date = doc.get('first_publish_year')
                            work.publisher = doc.get('publisher', [''])[0] if doc.get('publisher') else ''
                            work.authors = [{'name': name} for name in doc.get('author_name', [])]
                            work.identifiers = {'olid': [doc['olid']]} if 'olid' in doc else {'olid': [doc['key'].split('/')[-1]]}
                            works.append(work)
                        return works
                    else:
                        doc = data['docs'][0]
                        work = cls(doc['key'].split('/')[-1])
                        work.title = doc['title']
                        work.publish_date = doc.get('first_publish_year')
                        work.publisher = doc.get('publisher', [''])[0] if doc.get('publisher') else ''
                        work.authors = [{'name': name} for name in doc.get('author_name', [])]
                        work.identifiers = {'olid': [doc['olid']]} if 'olid' in doc else {'olid': [doc['key'].split('/')[-1]]}
                        return work
                except Exception as e:
                    logger.error(f"Search failed: {e}")
                    raise
        
        return CachedWork

    @property
    def Work(self):
        """Override the Work property to return our cached version"""
        return self._cached_work_class

    def get_ol_response(self, path):
        """Override get_ol_response to implement caching"""
        full_url = self.base_url + path
        return self._make_request(full_url) 