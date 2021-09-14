from django.db import models

class Author(models.Model):
    """Local representation of an author, based on OpenLibrary information"""
    # Display name to be used here (various other forms will always exist)
    primary_name = models.CharField(max_length=100)
    # Open Library ID, which uniquely identifies
    olid = models.CharField(max_length=100, primary_key=True)
