from django.db import models
from book.models.author import Author

class Work(models.Model):
    """
    Core intellectual content created by author(s), independent of format.
    
    For a popular book like Dune which has been printed in many editions and ISBNs,
    there will be a single Work object. This is similar to the previous Book model
    but with expanded capabilities for multiple authors and component works.
    """
    id = models.BigAutoField(primary_key=True)
    
    # Core metadata
    title = models.CharField(max_length=100)
    authors = models.ManyToManyField(Author)
    original_publication_date = models.DateField(null=True, blank=True)
    
    # Work type and relationships
    TYPE_CHOICES = [
        ('NOVEL', 'Novel'),
        ('SHORT_STORY', 'Short Story'),
        ('ANTHOLOGY', 'Anthology'),
        ('COLLECTION', 'Collection'),
    ]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    component_works = models.ManyToManyField('self', 
                                           symmetrical=False, 
                                           blank=True,
                                           related_name='contained_in')
    
    # Search and external data
    search_name = models.CharField(max_length=100, blank=True, null=True)
    olid = models.CharField(max_length=100)
    
    class Meta:
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['olid']),
        ]
    
    def __str__(self):
        return f"{self.title} by {', '.join(str(author) for author in self.authors.all())}"
