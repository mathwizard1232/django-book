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
        self._cached_author_class = self._create_cached_author()

    def _make_request(self, url, method='get', **kwargs):
        """Make a request with caching support"""
        # Try to get cached response for GET requests
        if method.lower() == 'get':
            cached_response = OpenLibraryCache.get_cached_response(url)
            if cached_response:
                logger.debug(f"Cache hit for {url}")
                logger.info("Cached response data: %s", cached_response)
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
                    logger.info("Raw response data before caching: %s", response_data)
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
                        logger.info("No docs found in OpenLibrary response")
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
                        logger.info("Multiple results found in OpenLibrary response")
                        return works
                    else:
                        logger.info("Single result found in OpenLibrary response")
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

            @classmethod
            def search_by_isbn(cls, isbn):
                """Search for a work using an ISBN with caching support"""
                # Clean ISBN
                isbn = isbn.replace('-', '').strip()
                
                # Use search API with ISBN
                url = f"{ol_instance.base_url}/search.json?isbn={isbn}"
                
                logger.debug(f"Making cached ISBN search request to {url}")
                try:
                    response = ol_instance._make_request(url)
                    data = response.json()
                    
                    if not data.get('docs'):
                        return None
                        
                    # Get first matching work
                    doc = data['docs'][0]
                    
                    # Create Work object
                    work = cls(doc['key'].split('/')[-1])
                    work.title = doc['title']
                    work.publish_date = doc.get('first_publish_year')
                    work.publisher = doc.get('publisher', [''])[0] if doc.get('publisher') else ''
                    
                    # Create author objects as dictionaries with name and optional olid
                    work.authors = []
                    for i, name in enumerate(doc.get('author_name', [])):
                        author = {'name': name}
                        if 'author_key' in doc and i < len(doc['author_key']):
                            author['olid'] = doc['author_key'][i]
                        work.authors.append(author)
                        
                    # Add identifiers
                    work.identifiers = {'olid': [doc['key'].split('/')[-1]]}
                    if 'isbn' in doc:
                        for isbn in doc['isbn']:
                            key = 'isbn_13' if len(isbn) == 13 else 'isbn_10'
                            if key not in work.identifiers:
                                work.identifiers[key] = []
                            work.identifiers[key].append(isbn)
                    
                    return work
                except Exception as e:
                    logger.error(f"ISBN search failed: {e}")
                    raise
        
        return CachedWork

    def _create_cached_author(self):
        """Create a cached version of the Author class"""
        original_author = super().Author
        ol_instance = self
        
        class CachedAuthor(original_author):
            @classmethod
            def search(cls, q, limit=5):
                """Search for authors with caching support"""
                url = f"{ol_instance.base_url}/authors/_autocomplete?q={q}&limit={limit}"
                
                logger.debug(f"Making cached author search request to {url}")
                try:
                    response = ol_instance._make_request(url)
                    return response.json()
                except Exception as e:
                    logger.error(f"Author search failed: {e}")
                    raise
                    
            @classmethod
            def get(cls, olid):
                """Get author details with caching support"""
                url = f"{ol_instance.base_url}/authors/{olid}.json"
                
                logger.debug(f"Making cached author get request to {url}")
                try:
                    response = ol_instance._make_request(url)
                    return response.json()  # Just return the raw JSON data
                except Exception as e:
                    logger.error(f"Author get failed: {e}")
                    raise
        
        return CachedAuthor

    @property
    def Work(self):
        """Override the Work property to return our cached version"""
        return self._cached_work_class

    @property
    def Author(self):
        """Override the Author property to return our cached version"""
        return self._cached_author_class

    def get_ol_response(self, path):
        """Override get_ol_response to implement caching"""
        full_url = self.base_url + path
        return self._make_request(full_url) 