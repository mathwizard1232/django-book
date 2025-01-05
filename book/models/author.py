from django.db import models

class Author(models.Model):
    """
    Local representation of an author, based on OpenLibrary information"""
    # Open Library ID
    # TODO: This isn't actually a perfect unique identifier. We should handle OpenLibrary duplicates
    # However, we can keep this as a primary key because we will choose their primary one as our stable base.
    # Eventually we can record duplicates and try to figure out how to feed that back into their system too.
    olid = models.CharField(max_length=100, primary_key=True)

    # Display name to be used here (various other forms will always exist)
    primary_name = models.CharField(max_length=100)

    # Search prefix used in initial lookup
    search_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.primary_name
