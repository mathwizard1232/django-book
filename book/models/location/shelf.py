from django.db import models

class Shelf(models.Model):
    """
    Represents a single shelf within a Bookcase.
    Position numbers start from 1 (top) and increment downward.
    """
    id = models.BigAutoField(primary_key=True)
    bookcase = models.ForeignKey('Bookcase', on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    book_groups = models.ManyToManyField('BookGroup', blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['bookcase', 'position']),
        ]
        unique_together = [['bookcase', 'position']]
        ordering = ['bookcase', 'position']
    
    def __str__(self):
        return f"Shelf {self.position} of {self.bookcase}"
    
    def get_location_path(self):
        """Returns the complete location path to this shelf"""
        bookcase = self.bookcase
        if bookcase.room:
            return f"{bookcase.room.location} > {bookcase.room} > {bookcase} > Shelf {self.position}"
        return f"{bookcase.location} > {bookcase} > Shelf {self.position}"