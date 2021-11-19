from django.db import models

from book.models.author import Author

class Book(models.Model):
    """
    Local representation of a particular set of content.

    For a popular book like Dune which has been printed in many editions and ISBNs,
    there will be a single Book object.

    Short stories are additionally handled separately. They are related to Book by
    being contained in various Books. This is, unfortunately, rather complicated.
    TODO: Build out ShortStory and relationship mapping many-to-many between Book and ShortStory
    """
    # We assign our own "serial number" style ids for books locally arbitrarily.
    # This is the same as the default setting but written explicitly
    id = models.BigAutoField(primary_key=True)

    # Author of the Book
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

    # Display Title of the Book (could be its own model in the future)
    title = models.CharField(max_length=100)

    # Entry initially given in first search
    search_name = models.CharField(max_length=100, blank=True, null=True)

    # Open Library ID, which unfortunately is not always a perfect unique ID for our concept of Book
    # In some cases there will be multiple Open Library IDs apparently referring to what we consider a single Book
    # We will here list the *primary* olid in our view and in future build out alternate olid support
    olid = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['olid'], name="book_olid"),  # Although multiple olid may be one Book, any given olid cannot be two Books
        ]
        unique_together = [
            ("author", "title"),  # There may be many books sharing the same title, but for a given author, only one Book per title please
        ]
