from django.core.management.base import BaseCommand
from book.models import Bookcase, Shelf

class Command(BaseCommand):
    help = 'Initialize shelves for bookcases that are missing them'

    def handle(self, *args, **options):
        bookcases = Bookcase.objects.all()
        shelves_created = 0

        for bookcase in bookcases:
            existing_shelf_count = Shelf.objects.filter(bookcase=bookcase).count()
            
            # Only create shelves if none exist
            if existing_shelf_count == 0:
                for position in range(1, bookcase.shelf_count + 1):
                    Shelf.objects.create(
                        bookcase=bookcase,
                        position=position
                    )
                    shelves_created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created {bookcase.shelf_count} shelves for bookcase "{bookcase.name}"'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully initialized {shelves_created} shelves'
            )
        )
