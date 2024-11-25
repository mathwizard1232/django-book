from django.db import models
from book.models.edition import Edition

class Copy(models.Model):
    """
    Physical instance of an Edition owned by the library.
    
    Represents a specific physical book that exists in the collection,
    with its own condition, location, and history.
    """
    id = models.BigAutoField(primary_key=True)
    
    # Core relationships
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE)
    
    # Physical characteristics
    CONDITION_CHOICES = [
        ('NEW', 'New'),
        ('LIKE_NEW', 'Like New'),
        ('VERY_GOOD', 'Very Good'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
    ]
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    
    # Acquisition details
    acquisition_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Location tracking (nullable for "unshelved" status)
    location = models.ForeignKey('Location', null=True, blank=True, on_delete=models.SET_NULL)
    room = models.ForeignKey('Room', null=True, blank=True, on_delete=models.SET_NULL)
    bookcase = models.ForeignKey('Bookcase', null=True, blank=True, on_delete=models.SET_NULL)
    shelf = models.ForeignKey('Shelf', null=True, blank=True, on_delete=models.SET_NULL)
    box = models.ForeignKey('Box', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Additional information
    notes = models.TextField(blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['edition']),
            models.Index(fields=['location']),
            models.Index(fields=['box']),
        ]
    
    def __str__(self):
        location_str = "Unshelved"
        if self.box:
            location_str = f"in {self.box}"
        elif self.shelf:
            location_str = f"on {self.shelf}"
        elif self.bookcase:
            location_str = f"in {self.bookcase}"
        elif self.room:
            location_str = f"in {self.room}"
        elif self.location:
            location_str = f"at {self.location}"
        return f"{self.edition} ({self.condition}) - {location_str}"