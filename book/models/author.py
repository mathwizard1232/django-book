from django.db import models
from django.db.models.manager import Manager
from book.utils.ol_client import CachedOpenLibrary
import logging

logger = logging.getLogger(__name__)

class AuthorManager(Manager):
    def get_or_fetch(self, olid):
        """Get author from local DB or fetch from OpenLibrary if not found"""
        try:
            return self.get(olid=olid)
        except self.model.DoesNotExist:
            # Attempt to fetch from OpenLibrary
            ol = CachedOpenLibrary()
            try:
                ol_author = ol.Author.get(olid)
                author = self.create(
                    olid=olid,
                    primary_name=ol_author.name,
                    search_name=ol_author.name
                )
                logger.info("Created new author record for %s (%s)", ol_author.name, olid)
                return author
            except Exception as e:
                logger.error("Failed to fetch author from OpenLibrary: %s", e)
                raise self.model.DoesNotExist(f"Author not found locally or in OpenLibrary: {olid}")

class Author(models.Model):
    """Local representation of an author, based on OpenLibrary information"""
    # Open Library ID
    # TODO: This isn't actually a perfect unique identifier. We should handle OpenLibrary duplicates
    # However, we can keep this as a primary key because we will choose their primary one as our stable base.
    # Eventually we can record duplicates and try to figure out how to feed that back into their system too.
    olid = models.CharField(max_length=100, primary_key=True)

    # Display name to be used here (various other forms will always exist)
    primary_name = models.CharField(max_length=100)

    # Search prefix used in initial lookup
    search_name = models.CharField(max_length=100, blank=True, null=True)

    # Use our custom manager
    objects = AuthorManager()

    def __str__(self):
        return self.primary_name
