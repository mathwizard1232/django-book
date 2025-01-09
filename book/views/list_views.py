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
    )
    
    logger.info("Found %d total works to process", works.count())
    
    # Group works by location > bookcase > shelf
    works_by_location = {}
    unassigned_works = []
    displayed_component_works = set()  # Track which component works we've handled
    displayed_parent_works = set()  # Track which parent works we've handled
    
    # First pass: Handle parent multivolume works
    logger.info("Starting first pass: handling parent multivolume works")
    for work in works:
        if not work.is_multivolume or work.volume_number:
            continue
            
        logger.info("Processing potential parent work: %s (id=%d)", work.title, work.id)
        
        # Skip parent works that don't have component works
        if not work.component_works.exists():
            logger.info("Skipping work %d: no component works", work.id)
            continue
            
        # This is a parent multivolume work
        component_shelves = set()
        component_volumes = {}
        all_volumes_found = True
        
        logger.info("Found parent multivolume work: %s (id=%d)", work.title, work.id)
        
        # Check locations of all component volumes
        for component in work.component_works.all():
            logger.info("Checking component work: %s (id=%d)", component.title, component.id)
            has_copies = False
            for edition in component.edition_set.all():
                for copy in edition.copy_set.all():
                    has_copies = True
                    if copy.shelf:
                        shelf_id = copy.shelf.id
                        component_shelves.add(shelf_id)
                        if shelf_id not in component_volumes:
                            component_volumes[shelf_id] = []
                        component_volumes[shelf_id].append(component)
                        logger.info("Component %d found on shelf %d", component.id, shelf_id)
            if not has_copies:
                logger.info("Component %d has no copies", component.id)
                all_volumes_found = False
        
        logger.info("Component analysis for work %d:", work.id)
        logger.info("- Shelves found: %s", component_shelves)
        logger.info("- All volumes found: %s", all_volumes_found)
        
        # Only show as a set if all volumes are present and on the same shelf
        # AND we have more than one volume
        shelf_id = next(iter(component_shelves)) if component_shelves else None
        if shelf_id and len(component_shelves) == 1 and all_volumes_found and len(component_volumes[shelf_id]) > 1:
            copy = edition.copy_set.filter(shelf_id=shelf_id).first()
            if copy:
                location_name = copy.location.name if copy.location else copy.room.location.name
                bookcase_name = copy.bookcase.name
                shelf_position = copy.shelf.position
                
                logger.info("Adding complete set to location: %s > %s > %d", 
                           location_name, bookcase_name, shelf_position)
                
                if location_name not in works_by_location:
                    works_by_location[location_name] = {}
                if bookcase_name not in works_by_location[location_name]:
                    works_by_location[location_name][bookcase_name] = {}
                if shelf_position not in works_by_location[location_name][bookcase_name]:
                    works_by_location[location_name][bookcase_name][shelf_position] = []
                
                work.volume_count = len(component_volumes[shelf_id])
                works_by_location[location_name][bookcase_name][shelf_position].append(work)
                displayed_parent_works.add(work.id)  # Mark parent work as displayed
                logger.info("Added parent work %d with %d volumes", work.id, work.volume_count)
                
                # Mark all components as displayed
                for component in component_volumes[shelf_id]:
                    displayed_component_works.add(component.id)
                    logger.info("Marked component %d as displayed", component.id)
        else:
            # If volumes are spread across shelves or incomplete, mark the parent as "displayed"
            # so it won't show up in unassigned
            displayed_parent_works.add(work.id)
            logger.info("Marked incomplete/spread parent work %d as displayed", work.id)
    
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
