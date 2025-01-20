from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class Bookcase(models.Model):
    """
    Represents a physical storage unit for books.
    Can belong to either a Room or directly to a Location.
    """
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    shelf_count = models.PositiveIntegerField()
    
    # Location hierarchy - only one of these should be set
    location = models.ForeignKey('Location', null=True, blank=True, on_delete=models.CASCADE)
    room = models.ForeignKey('Room', null=True, blank=True, on_delete=models.CASCADE)
    
    # Optional grouping
    book_groups = models.ManyToManyField('BookGroup', blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['location']),
            models.Index(fields=['room']),
            models.Index(fields=['name']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(location__isnull=False, room__isnull=True) |
                    models.Q(location__isnull=True, room__isnull=False)
                ),
                name='bookcase_single_parent'
            )
        ]
    
    def __str__(self):
        parent = self.room if self.room else self.location
        return f"{self.name} in {parent}"
    
    def get_location(self):
        """Returns the top-level Location this bookcase belongs to"""
        if self.location:
            return self.location
        return self.room.location if self.room else None

@receiver(post_save, sender=Bookcase)
def create_shelves(sender, instance, created, **kwargs):
    """
    Creates shelf objects for each position in a new bookcase.
    Only runs on initial creation, not updates.
    """
    if created:  # only run on new bookcase creation
        from .shelf import Shelf
        for position in range(1, instance.shelf_count + 1):
            Shelf.objects.create(
                bookcase=instance,
                position=position
            )