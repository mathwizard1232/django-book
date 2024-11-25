from django.db import models

class Box(models.Model):
    """
    Represents a container for books that can be moved as a unit.
    Can belong to either a Room or directly to a Location.
    """
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    dimensions = models.CharField(max_length=100, null=True, blank=True)
    
    # Location hierarchy - only one of these should be set
    location = models.ForeignKey('Location', null=True, blank=True, on_delete=models.CASCADE)
    room = models.ForeignKey('Room', null=True, blank=True, on_delete=models.CASCADE)
    
    STATUS_CHOICES = [
        ('SEALED', 'Sealed'),
        ('UNSEALED', 'Unsealed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNSEALED')
    
    # Optional grouping
    book_groups = models.ManyToManyField('BookGroup', blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['location']),
            models.Index(fields=['room']),
            models.Index(fields=['name']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(location__isnull=False, room__isnull=True) |
                    models.Q(location__isnull=True, room__isnull=False)
                ),
                name='box_single_parent'
            )
        ]
    
    def __str__(self):
        parent = self.room if self.room else self.location
        return f"Box: {self.name} in {parent}"
    
    def get_location(self):
        """Returns the top-level Location this box belongs to"""
        if self.location:
            return self.location
        return self.room.location if self.room else None