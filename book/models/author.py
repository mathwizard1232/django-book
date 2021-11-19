from django.db import models

class Author(models.Model):
    """Local representation of an author, based on OpenLibrary information"""
    # Open Library ID, which uniquely identifies
    # Unlike on Book, for Author an olid is a strong identification
    olid = models.CharField(max_length=100, primary_key=True)

    # Display name to be used here (various other forms will always exist)
    primary_name = models.CharField(max_length=100)

    # Search prefix used in initial lookup
    search_name = models.CharField(max_length=100, blank=True, null=True)
