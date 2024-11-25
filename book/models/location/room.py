from django.db import models

class Room(models.Model):
    """
    Represents a distinct room or space within a Location.
    Examples: master bedroom, living room, basement, etc.
    """
    id = models.BigAutoField(primary_key=True)
    location = models.ForeignKey('Location', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    
    TYPE_CHOICES = [
        ('BEDROOM', 'Bedroom'),
        ('LIVING', 'Living Room'),
        ('OFFICE', 'Office/Study'),
        ('LIBRARY', 'Library'),
        ('STORAGE', 'Storage Room'),
        ('BASEMENT', 'Basement'),
        ('ATTIC', 'Attic'),
        ('OTHER', 'Other'),
    ]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    floor = models.IntegerField(default=1)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['location', 'name']),
            models.Index(fields=['type']),
        ]
        unique_together = [['location', 'name']]
    
    def __str__(self):
        return f"{self.name} in {self.location}"
    
    def full_name(self):
        """Returns the complete location path"""
        return f"{self.location} - {self.name}"