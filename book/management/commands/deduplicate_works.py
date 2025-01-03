from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from book.models import Work, Edition, Copy
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Identifies and merges duplicate Works in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        # Find Works with same title and authors
        works = Work.objects.annotate(
            author_count=Count('authors')
        ).prefetch_related('authors').all()
        
        self.stdout.write(f'Found {works.count()} total works')
        
        # Group works by normalized title and author set
        work_groups = {}
        for work in works:
            # Create a key from normalized title and sorted author OLIDs
            title_key = work.title.lower().strip()
            author_olids = tuple(sorted(
                work.authors.all().values_list('olid', flat=True)
            ))
            group_key = (title_key, author_olids)
            
            # Debug output
            self.stdout.write(f'Work: "{work.title}" (ID: {work.id})')
            self.stdout.write(f'  Normalized title: "{title_key}"')
            self.stdout.write(f'  Authors: {author_olids}')
            
            if group_key not in work_groups:
                work_groups[group_key] = []
            work_groups[group_key].append(work)
        
        # Show all groups
        self.stdout.write('\nGroups found:')
        for (title, authors), works in work_groups.items():
            self.stdout.write(f'Group: "{title}" with authors {authors}:')
            for work in works:
                self.stdout.write(f'  - Work ID: {work.id}, Title: "{work.title}"')
        
        # Filter to only groups with duplicates
        potential_duplicates = [
            group for group in work_groups.values()
            if len(group) > 1
        ]

        if not potential_duplicates:
            self.stdout.write('No duplicate works found')
            return

        self.stdout.write(f'Found {len(potential_duplicates)} groups of duplicate works')

        for group in potential_duplicates:
            self._handle_duplicate_group(group, dry_run=options['dry_run'])

    def _are_works_duplicate(self, work1, work2):
        """Check if two works are duplicates based on title and authors"""
        # Normalize titles for comparison (lowercase, strip whitespace)
        title1 = work1.title.lower().strip()
        title2 = work2.title.lower().strip()
        
        if title1 != title2:
            return False
            
        # Get sets of author IDs for comparison
        authors1 = set(work1.authors.all().values_list('id', flat=True))
        authors2 = set(work2.authors.all().values_list('id', flat=True))
        
        # Log potential duplicates for verification
        if authors1 == authors2:
            self.stdout.write(
                f"Found potential duplicate: '{work1.title}' (ID: {work1.id}) and '{work2.title}' (ID: {work2.id})"
            )
        
        return authors1 == authors2

    def _select_primary_work(self, works):
        """Select the most complete work record to keep"""
        # Prefer works with:
        # 1. Original publication date
        # 2. More complete metadata
        # 3. More editions
        # 4. Earlier ID (older record)
        return sorted(works, key=lambda w: (
            w.original_publication_date is not None,
            bool(w.search_name),
            w.edition_set.count(),
            -w.id
        ), reverse=True)[0]

    def _handle_duplicate_group(self, works, dry_run=False):
        primary_work = self._select_primary_work(works)
        
        self.stdout.write(f'\nHandling duplicates for "{primary_work.title}"')
        self.stdout.write(f'Primary work ID: {primary_work.id}')
        
        for work in works:
            if work.id == primary_work.id:
                continue
                
            self.stdout.write(f'  Merging work ID {work.id}')
            
            if dry_run:
                continue
                
            try:
                with transaction.atomic():
                    # Move editions to primary work
                    Edition.objects.filter(work=work).update(work=primary_work)
                    
                    # Delete the duplicate work
                    work.delete()
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'  Successfully merged work ID {work.id} into {primary_work.id}'
                    ))
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  Failed to merge work ID {work.id}: {str(e)}')
                )