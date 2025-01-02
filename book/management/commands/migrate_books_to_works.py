from django.core.management.base import BaseCommand
from django.db import transaction
from book.models import Book, Work, Edition, Copy, Author
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrates existing Book records to Work/Edition/Copy structure'

    def handle(self, *args, **options):
        books = Book.objects.all()
        migrated_count = 0
        skipped_count = 0

        self.stdout.write(f"Found {books.count()} Books to process")

        for book in books:
            try:
                with transaction.atomic():
                    # Check if Work already exists for this OLID
                    work = Work.objects.filter(olid=book.olid).first()
                    
                    if not work:
                        # Create Work
                        work = Work.objects.create(
                            title=book.title,
                            search_name=book.search_name,
                            olid=book.olid,
                            type='NOVEL'  # Default type as used in confirm_book view
                        )
                        # Add author relationship
                        work.authors.add(book.author)
                        
                        # Create default Edition
                        edition = Edition.objects.create(
                            work=work,
                            publisher="Unknown",  # Default as used in confirm_book view
                            format="PAPERBACK"    # Default as used in confirm_book view
                        )
                        
                        # Create default Copy
                        Copy.objects.create(
                            edition=edition,
                            condition="GOOD"  # Default as used in confirm_book view
                        )
                        
                        migrated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Successfully migrated Book "{book.title}" by {book.author.primary_name}'
                            )
                        )
                    else:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f'Skipped Book "{book.title}" - Work already exists'
                            )
                        )
                        
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Failed to migrate Book "{book.title}": {str(e)}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Migration complete. Migrated: {migrated_count}, Skipped: {skipped_count}'
            )
        )