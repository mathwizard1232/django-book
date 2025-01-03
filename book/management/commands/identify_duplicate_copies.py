from django.core.management.base import BaseCommand
from django.db.models import Count
from book.models import Copy, Edition, Work
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Identifies potential duplicate Copies that may represent the same physical book'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--include-shelved',
            action='store_true',
            help='Include shelved copies in duplicate detection',
        )

    def handle(self, *args, **options):
        # Get all copies or just unshelved ones based on flag
        copies_query = Copy.objects.all() if options['include_shelved'] else Copy.objects.filter(
            shelf__isnull=True,
            box__isnull=True
        )
        
        copies = copies_query.select_related(
            'edition__work',
            'location',
            'room',
            'bookcase',
            'shelf'
        )

        # Group by Work
        work_groups = {}
        for copy in copies:
            work = copy.edition.work
            if work.id not in work_groups:
                work_groups[work.id] = []
            work_groups[work.id].append(copy)

        # Find groups with multiple copies
        duplicate_groups = {
            work_id: copies for work_id, copies in work_groups.items()
            if len(copies) > 1
        }

        if not duplicate_groups:
            self.stdout.write('No potential duplicate copies found')
            return

        self.stdout.write(f'Found {len(duplicate_groups)} works with multiple copies:')
        
        for work_id, copies in duplicate_groups.items():
            work = copies[0].edition.work
            self.stdout.write(f'\nWork: "{work.title}" has {len(copies)} copies:')
            for copy in copies:
                location_str = self._get_location_string(copy)
                self.stdout.write(
                    f'  Copy ID: {copy.id}, '
                    f'Location: {location_str}, '
                    f'Added: {copy.acquisition_date or "Unknown"}, '
                    f'Condition: {copy.condition}'
                )

            if not options['dry_run']:
                self._prompt_for_merge(copies)

    def _get_location_string(self, copy):
        """Generate a human-readable location string for a copy"""
        if copy.shelf:
            return f"{copy.bookcase.name} > Shelf {copy.shelf.position}"
        if copy.bookcase:
            return f"{copy.bookcase.name}"
        if copy.room:
            return f"{copy.room.name}"
        if copy.location:
            return f"{copy.location.name}"
        return "Unassigned"

    def _prompt_for_merge(self, copies):
        """Interactive prompt to handle duplicate copies"""
        while True:
            response = input('\nMerge these copies? (y/n/q): ').lower()
            if response == 'q':
                return
            if response in ('y', 'n'):
                break

        if response == 'y':
            # Keep the first copy, delete others
            primary_copy = copies[0]
            for copy in copies[1:]:
                self.stdout.write(f'Deleting copy {copy.id}...')
                copy.delete()
            self.stdout.write(self.style.SUCCESS('Copies merged successfully'))