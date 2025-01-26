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
    # For instance, we might have "Frederick 'Max Brand' Faust"
    # This should be our best "presentation" name (may have more information than search_name)
    # Balance between giving a more "proper" name but not necessarily unusual forms
    # e.g. J. R. R. Tolkien vs. John Ronald Reuel Tolkien; we would prefer the former
    primary_name = models.CharField(max_length=100)

    # Search prefix used in initial lookup
    # For instance, we might have "Max Brand" or "Tolkein" or "Heinlein"
    # This should be whatever the user is most likely to search for / most common form
    search_name = models.CharField(max_length=100, blank=True, null=True)

    # Birth date
    birth_date = models.CharField(max_length=50, blank=True, null=True)

    # Death date
    death_date = models.CharField(max_length=50, blank=True, null=True)

    # Alternate names
    alternate_names = models.JSONField(default=list, blank=True)

    # Alternate Open Library IDs
    alternate_olids = models.JSONField(default=list, blank=True)

    # Use our custom manager
    objects = AuthorManager()

    def __str__(self):
        return self.primary_name

    def display_name(self):
        """Return name with dates if available"""
        if self.birth_date and self.death_date:
            return f"{self.primary_name} ({self.birth_date}-{self.death_date})"
        return self.primary_name
