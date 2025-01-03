from django.db import models
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class OpenLibraryCache(models.Model):
    """Cache for OpenLibrary API responses to reduce API calls"""
    
    # The full URL of the API request
    request_url = models.CharField(max_length=2000, primary_key=True)
    
    # The response data stored as JSON
    response_data = models.JSONField()
    
    # When this cache entry was last updated
    last_updated = models.DateTimeField(auto_now=True)
    
    # How long this cache entry should be considered valid (in hours)
    # Different types of requests might have different cache durations
    cache_duration = models.IntegerField(default=24)
    
    class Meta:
        indexes = [
            models.Index(fields=['last_updated']),
        ]
    
    @property
    def is_valid(self):
        """Check if the cache entry is still valid"""
        expiry_time = self.last_updated + timedelta(hours=self.cache_duration)
        return datetime.now().astimezone() < expiry_time
    
    @classmethod
    def get_cached_response(cls, url: str) -> dict:
        """Get a cached response if it exists and is valid"""
        try:
            cache_entry = cls.objects.get(request_url=url)
            logger.debug(f"Found cache entry for {url}")
            
            if cache_entry.is_valid:
                logger.debug(f"Cache hit for {url}")
                return cache_entry.response_data
                
            logger.debug(f"Cache expired for {url}")
            # Delete expired cache entry
            cache_entry.delete()
        except cls.DoesNotExist:
            logger.debug(f"No cache entry found for {url}")
        return None
    
    @classmethod
    def cache_response(cls, url: str, response_data: dict, duration: int = 24):
        """Cache a response from the OpenLibrary API"""
        try:
            cls.objects.update_or_create(
                request_url=url,
                defaults={
                    'response_data': response_data,
                    'cache_duration': duration
                }
            )
            logger.debug(f"Successfully cached response for {url}")
        except Exception as e:
            logger.error(f"Failed to cache response for {url}: {e}") 