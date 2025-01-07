from django.shortcuts import render
from django.db.models import Count
from ..models import Author, Work, Copy, Location

def list(request):
    """Display summary of what's in library"""
    # Get authors who have at least one work, sorted by last name
    authors_with_works = Author.objects.filter(work__isnull=False).distinct()
    authors_with_works = sorted(
        authors_with_works,
        key=lambda x: x.primary_name.split()[-1].lower()
    )
    
    # Calculate statistics
    total_authors = len(authors_with_works)
    total_copies = Copy.objects.count()
    total_works = Work.objects.filter(
        edition__copy__isnull=False,
        is_multivolume=False  # Only count individual volumes
    ).distinct().count()
    
    # Get works and organize by location hierarchy
    works = Work.objects.filter(
        is_multivolume=False
    ).prefetch_related(
        'authors',
        'edition_set__copy_set__location',
        'edition_set__copy_set__room',
        'edition_set__copy_set__bookcase',
        'edition_set__copy_set__shelf'
    ).annotate(
        copy_count=Count('edition__copy')
    )
    
    # Group works by location > bookcase > shelf
    works_by_location = {}
    unassigned_works = []
    
    for work in works:
        has_assigned_location = False
        for edition in work.edition_set.all():
            for copy in edition.copy_set.all():
                if copy.shelf and copy.bookcase:
                    location_name = copy.location.name if copy.location else copy.room.location.name
                    bookcase_name = copy.bookcase.name
                    shelf_position = copy.shelf.position
                    
                    if location_name not in works_by_location:
                        works_by_location[location_name] = {}
                    if bookcase_name not in works_by_location[location_name]:
                        works_by_location[location_name][bookcase_name] = {}
                    if shelf_position not in works_by_location[location_name][bookcase_name]:
                        works_by_location[location_name][bookcase_name][shelf_position] = []
                    
                    if work not in works_by_location[location_name][bookcase_name][shelf_position]:
                        works_by_location[location_name][bookcase_name][shelf_position].append(work)
                        has_assigned_location = True
        
        if not has_assigned_location:
            unassigned_works.append(work)

    # Sort the dictionaries
    works_by_location = {
        loc: {
            bookcase: dict(sorted(shelves.items()))
            for bookcase, shelves in bookcases.items()
        }
        for loc, bookcases in sorted(works_by_location.items())
    }

    context = {
        'authors': authors_with_works,
        'works_by_location': works_by_location,
        'unassigned_works': unassigned_works,
        'stats': {
            'total_authors': total_authors,
            'total_copies': total_copies,
            'total_works': total_works,
        }
    }
    return render(request, 'list.html', context)
