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

    def handle(self, *args, **options):
        # Find unshelved copies grouped by Work
        unshelved_copies = Copy.objects.filter(
            shelf__isnull=True,
            box__isnull=True
        ).select_related(
            'edition__work'
        )

        # Group by Work
        work_groups = {}
        for copy in unshelved_copies:
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

        self.stdout.write(f'Found {len(duplicate_groups)} works with multiple unshelved copies:')
        
        for work_id, copies in duplicate_groups.items():
            work = copies[0].edition.work
            self.stdout.write(f'\nWork: "{work.title}" has {len(copies)} unshelved copies:')
            for copy in copies:
                self.stdout.write(
                    f'  Copy ID: {copy.id}, '
                    f'Added: {copy.acquisition_date or "Unknown"}, '
                    f'Condition: {copy.condition}'
                )

            if not options['dry_run']:
                self._prompt_for_merge(copies)

    def _prompt_for_merge(self, copies):
        while True:
            self.stdout.write('\nOptions:')
            self.stdout.write('  [k] Keep all copies (they are different physical books)')
            self.stdout.write('  [m] Merge copies (they are the same physical book)')
            self.stdout.write('  [s] Skip this group')
            
            choice = input('Choose action: ').lower()
            
            if choice == 'k':
                self.stdout.write('Keeping all copies')
                break
            elif choice == 'm':
                # Keep the oldest copy (by ID if no acquisition date)
                primary_copy = sorted(
                    copies,
                    key=lambda c: (c.acquisition_date or '9999-12-31', c.id)
                )[0]
                
                for copy in copies:
                    if copy.id != primary_copy.id:
                        copy.delete()
                
                self.stdout.write(f'Merged copies, keeping Copy ID: {primary_copy.id}')
                break
            elif choice == 's':
                self.stdout.write('Skipped')
                break