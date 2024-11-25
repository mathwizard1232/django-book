from django.db import models

class Location(models.Model):
    """
    Represents a distinct physical building or storage space.
    Examples: house, storage unit, cabin, etc.
    """
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    
    TYPE_CHOICES = [
        ('HOUSE', 'House'),
        ('STORAGE', 'Storage Unit'),
        ('CABIN', 'Cabin'),
        ('OFFICE', 'Office'),
        ('OTHER', 'Other'),
    ]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"