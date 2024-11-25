from django.db import models

class BookGroup(models.Model):
    """
    Represents a logical collection of books that share a common organization scheme.
    Can span multiple physical locations, bookcases, or shelves.
    """
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    
    SCHEME_CHOICES = [
        ('ALPHA_AUTHOR', 'Alphabetical by Author'),
        ('ALPHA_TITLE', 'Alphabetical by Title'),
        ('PUB_DATE', 'By Publication Date'),
        ('GENRE', 'By Genre'),
        ('SERIES', 'By Series'),
        ('CUSTOM', 'Custom Organization'),
    ]
    organization_scheme = models.CharField(max_length=20, choices=SCHEME_CHOICES)
    
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['organization_scheme']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_organization_scheme_display()})"
    
    def get_copies(self):
        """Returns all Copies associated with this group"""
        from book.models.copy import Copy
        return Copy.objects.filter(
            models.Q(shelf__book_groups=self) |
            models.Q(box__book_groups=self)
        ).distinct()