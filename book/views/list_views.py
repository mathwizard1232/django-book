from django.shortcuts import render
from django.db.models import Count, Q, F, OuterRef, Subquery
from ..models import Author, Work, Copy, Location
import logging

logger = logging.getLogger(__name__)

def list(request):
    """Display summary of what's in library"""
    # Get authors who have at least one work, sorted by last name
    authors_with_works = Author.objects.filter(work__isnull=False).distinct()
    authors_with_works = sorted(
        authors_with_works,
        key=lambda x: x.primary_name.split()[-1].lower()
    )
    
    # Add work count to each author
    for author in authors_with_works:
        author.work_count = author.work_set.count() + author.edited_works.count()
    
    # Calculate statistics
    total_authors = len(authors_with_works)
    total_copies = Copy.objects.count()
    total_works = Work.objects.filter(
        edition__copy__isnull=False,
        is_multivolume=False  # Only count individual volumes
    ).distinct().count()
    
    logger.info("Starting list view processing")
    logger.info("Total authors: %d, copies: %d, works: %d", total_authors, total_copies, total_works)
    
    # Get works and organize by location hierarchy
    works = Work.objects.filter(
        Q(is_multivolume=False) |  # Individual volumes
        Q(is_multivolume=True, volume_number__isnull=True)  # Parent works
    ).prefetch_related(
        'authors',
        'editors',
        'component_works',
        'edition_set__copy_set__location',
        'edition_set__copy_set__room',
        'edition_set__copy_set__bookcase',
        'edition_set__copy_set__shelf'
    ).filter(edition__copy__isnull=False).distinct()  # Only include works that have copies
    
    logger.info("Found %d total works to process", works.count())
    
    # Group works by location > bookcase > shelf
    works_by_location = {}
    unassigned_works = []
    displayed_component_works = set()  # Track which component works we've handled
    displayed_parent_works = set()  # Track which parent works we've handled
    
    # First pass: Handle parent multivolume works and collections
    logger.info("Starting first pass: handling parent works")
    for work in works:
        if not work.is_multivolume and work.type != "COLLECTION":
            continue

        logger.info("Processing potential parent work: %s (id=%d)", work.title, work.id)

        # Skip parent works that don't have component works
        if not work.component_works.exists():
            logger.info("Skipping work %d: no component works", work.id)
            continue

        # Check if the parent work itself has a shelved copy
        for edition in work.edition_set.all():
            for copy in edition.copy_set.all():
                if copy.shelf:
                    # If the collection/parent work is shelved, mark all its components as displayed
                    displayed_component_works.update(
                        work.component_works.values_list('id', flat=True)
                    )
                    displayed_parent_works.add(work.id)
                    
                    location_name = copy.location.name if copy.location else copy.room.location.name
                    bookcase_name = copy.bookcase.name
                    shelf_position = copy.shelf.position

                    if location_name not in works_by_location:
                        works_by_location[location_name] = {}
                    if bookcase_name not in works_by_location[location_name]:
                        works_by_location[location_name][bookcase_name] = {}
                    if shelf_position not in works_by_location[location_name][bookcase_name]:
                        works_by_location[location_name][bookcase_name][shelf_position] = []

                    works_by_location[location_name][bookcase_name][shelf_position].append(work)
                    logger.info("Added shelved collection/parent work %d and marked components as displayed", work.id)
                    break
    
    logger.info("Starting second pass: handling individual volumes and non-multivolume works")
    logger.info("Currently displayed: %d parent works, %d component works", 
                len(displayed_parent_works), len(displayed_component_works))
    
    # Second pass: Handle individual volumes and non-multivolume works
    for work in works:
        if work.id in displayed_component_works or work.id in displayed_parent_works:
            logger.info("Skipping already displayed work: %s (id=%d)", work.title, work.id)
            continue
            
        # Skip invalid multivolume works (those without components)
        if work.is_multivolume and not work.volume_number and not work.component_works.exists():
            logger.info("Skipping invalid multivolume work without components: %s (id=%d)", 
                       work.title, work.id)
            continue
            
        logger.info("Processing work: %s (id=%d)", work.title, work.id)
        has_assigned_location = False
        shelf_copy_counts = {}  # Track copies per shelf for this work
        work_locations = set()  # Track unique location/bookcase/shelf combinations
        
        # First count all copies
        for edition in work.edition_set.all():
            for copy in edition.copy_set.all():
                if copy.shelf:
                    shelf_id = copy.shelf.id
                    if shelf_id not in shelf_copy_counts:
                        shelf_copy_counts[shelf_id] = 0
                    shelf_copy_counts[shelf_id] += 1
                    
                    location_name = copy.location.name if copy.location else copy.room.location.name
                    bookcase_name = copy.bookcase.name
                    shelf_position = copy.shelf.position
                    
                    work_locations.add((location_name, bookcase_name, shelf_position, shelf_id))
                    logger.info("Found copy on shelf: %s > %s > %d", 
                               location_name, bookcase_name, shelf_position)
        
        # Then add work to each unique shelf with the correct copy count
        for location_name, bookcase_name, shelf_position, shelf_id in work_locations:
            if location_name not in works_by_location:
                works_by_location[location_name] = {}
            if bookcase_name not in works_by_location[location_name]:
                works_by_location[location_name][bookcase_name] = {}
            if shelf_position not in works_by_location[location_name][bookcase_name]:
                works_by_location[location_name][bookcase_name][shelf_position] = []
            
            # Only add the work once per shelf
            if not any(w.id == work.id for w in works_by_location[location_name][bookcase_name][shelf_position]):
                work_copy = Work.objects.get(id=work.id)
                work_copy.shelf_copy_count = shelf_copy_counts[shelf_id]
                works_by_location[location_name][bookcase_name][shelf_position].append(work_copy)
                has_assigned_location = True
                logger.info("Added work %d to shelf with %d copies", 
                          work.id, shelf_copy_counts[shelf_id])
        
        # Only add to unassigned if it's not displayed anywhere and has no copies on shelves
        if not has_assigned_location and not any(copy.shelf for edition in work.edition_set.all() for copy in edition.copy_set.all()):
            unassigned_works.append(work)
            logger.info("Added work %d to unassigned works", work.id)

    logger.info("Final counts:")
    logger.info("- Locations: %d", len(works_by_location))
    logger.info("- Unassigned works: %d", len(unassigned_works))
    logger.info("- Displayed parent works: %d", len(displayed_parent_works))
    logger.info("- Displayed component works: %d", len(displayed_component_works))

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
