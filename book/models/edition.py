from django.db import models
from book.models.work import Work

class Edition(models.Model):
    """
    Specific published version of a Work.
    
    Represents a particular published form of a Work, with its own
    physical characteristics and identifiers. Multiple copies may exist
    of the same Edition.
    """
    id = models.BigAutoField(primary_key=True)
    
    # Core metadata
    work = models.ForeignKey(Work, on_delete=models.CASCADE)
    publisher = models.CharField(max_length=100)
    publication_date = models.DateField(null=True, blank=True)
    language = models.CharField(max_length=50, default='eng')
    
    # Physical characteristics
    FORMAT_CHOICES = [
        ('HARDCOVER', 'Hardcover'),
        ('PAPERBACK', 'Paperback'),
        ('EBOOK', 'E-Book'),
        ('AUDIO', 'Audiobook'),
    ]
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    page_count = models.IntegerField(null=True, blank=True)
    dimensions = models.CharField(max_length=100, null=True, blank=True)
    
    # Identifiers
    isbn = models.CharField(max_length=13, null=True, blank=True, unique=True)
    olid = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['isbn']),
            models.Index(fields=['olid']),
            models.Index(fields=['work', 'publisher', 'publication_date']),
        ]
    
    def __str__(self):
        return f"{self.work.title} ({self.publisher}, {self.publication_date.year if self.publication_date else 'Unknown'})"
