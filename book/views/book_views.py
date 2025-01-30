import logging
import urllib.parse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, JsonResponse, HttpResponseServerError
from django.shortcuts import render
from ..forms import TitleForm, TitleGivenAuthorForm, ConfirmBook, TitleOnlyForm, AuthorForm
from ..models import Author, Work, Edition, Copy, Location, Shelf
from ..utils.ol_client import CachedOpenLibrary
from .autocomplete_views import DIVIDER
from ..controllers.work_controller import WorkController
import json
import re
from ..utils.author_utils import format_primary_name
from django import forms

logger = logging.getLogger(__name__)

def get_title(request):
    """ Do a lookup of a book by title, with a particular author potentially already set """
    try:
        logger.info("=== Title Entry Request Details ===")
        logger.info("Session data: %s", dict(request.session))
        logger.info("POST data: %s", dict(request.POST))
        logger.info("GET data: %s", dict(request.GET))
        
        # Add logging for author context
        logger.info("=== Author Context ===")
        logger.info("Selected author OLID: %s", request.session.get('selected_author_olid'))
        logger.info("Selected author name: %s", request.session.get('selected_author_name'))
        
        # Collect first work data from GET or POST
        collection_data = {}
        if request.method == 'GET':
            for key in ['first_work_title', 'first_work_olid', 'first_work_author_names', 
                       'first_work_author_olids', 'first_work_publisher']:
                if value := request.GET.get(key):
                    collection_data[key] = value
        else:
            for key in ['first_work_title', 'first_work_olid', 'first_work_author_names', 
                       'first_work_author_olids', 'first_work_publisher']:
                if value := request.POST.get(key):
                    collection_data[key] = value

        logger.info("=== Collection Data in Title Entry ===")
        logger.info("Collection data: %s", collection_data)
        
        if request.method == 'GET':
            if 'author_olid' in request.GET:
                a_olid = request.GET['author_olid']
                author_name = request.GET['author_name']
                
                # Check if we need to create the Author
                if not Author.objects.filter(olid=a_olid).exists():
                    # Extract work count if present
                    work_count = None
                    if '(' in author_name and 'works)' in author_name:
                        base_name = author_name.split('(')[0].strip()
                        work_count = int(author_name.split('(')[1].split(' works)')[0])
                    
                    # If this is a high-quality match (significant work count), create Author
                    if work_count and work_count >= 100:  # We can adjust this threshold
                        # Extract base name without work count
                        search_name = author_name.split('(')[0].strip()
                        
                        # Fetch full author details from OpenLibrary
                        ol = CachedOpenLibrary()
                        author_details = ol.Author.get(a_olid)
                        
                        # Get OpenLibrary name (prefer personal_name if available)
                        ol_name = author_details.get('personal_name') or author_details.get('name')
                        
                        # Create author with complete information
                        Author.objects.create(
                            olid=a_olid,
                            primary_name=format_primary_name(search_name, ol_name),
                            search_name=search_name.lower(),
                            birth_date=author_details.get('birth_date'),
                            death_date=author_details.get('death_date'),
                            alternate_names=author_details.get('alternate_names', [])
                        )
                
                form = TitleGivenAuthorForm({
                    'author_olid': a_olid, 
                    'author_name': author_name,
                    'author_role': request.GET.get('author_role', 'AUTHOR')
                })
                # Add logging for form processing after form is created
                logger.info("=== Form Processing ===")
                logger.info("Form initial data: %s", {
                    'author_olid': a_olid,
                    'author_name': author_name,
                    'author_role': request.GET.get('author_role', 'AUTHOR')
                })
                logger.info("Form is valid: %s", form.is_valid())
                if not form.is_valid():
                    logger.error("Form errors: %s", form.errors)
                    
                # Attempting to override with runtime value for url as a kludge for how to pass the author OLID
                data_url = "/author/" + a_olid + "/title-autocomplete"
                logger.info("new data url %s", data_url)
                form.fields['title'].widget.attrs.update({
                    'autofocus': 'autofocus',
                    'class': 'basicAutoComplete',
                    'data-url': data_url,
                    'autocomplete': 'off'
                })
                
                # Add collection data to context
                return render(request, 'title.html', {
                    'form': form,
                    'collection_data': collection_data
                })
            else:
                form = TitleForm()
                return render(request, 'title.html', {
                    'form': form,
                    'collection_data': collection_data
                })
        
        if request.method == 'POST':
            # Create a new GET-style request with the POST data
            get_request = request.GET.copy()
            get_request.update({
                'title': request.POST.get('title'),
                'author_olid': request.POST.get('author_olid'),
                'author_name': request.POST.get('author_name')
            })
            # Add collection data to GET request
            for key, value in collection_data.items():
                get_request[key] = value
            request.GET = get_request
            return _handle_book_search(request)
            
    except Exception as e:
        logger.exception("Unhandled exception in get_title")
        return HttpResponseServerError(f"Error processing title: {str(e)}")

def confirm_book(request):
    """ Given enough information for a lookup, retrieve the most likely book and confirm it's correct """
    logger.info("=== Book Confirmation Request Details ===")
    logger.info("Session collection_first_work: %s", request.session.get('collection_first_work'))
    logger.info("GET params first_work data: %s", {
        k: v for k, v in request.GET.items() if k.startswith('first_work_')
    })
    logger.info("POST params first_work data: %s", {
        k: v for k, v in request.POST.items() if k.startswith('first_work_')
    })

    if request.method == 'POST':
        return WorkController(request).handle_book_confirmation()  # Try new controller
    else:
        return _handle_book_search(request)

def _format_pen_name(real_name, pen_name, alternate_names):
    """Format author name to include pen name if appropriate.
    
    Args:
        real_name (str): The author's real name (e.g., "Frederick Schiller Faust")
        pen_name (str): The author's pen name (e.g., "Max Brand")
        alternate_names (list): List of alternate names to check against
        
    Returns:
        str: Formatted name with pen name in quotes if appropriate, or original name
    """
    # Split names into components and just use first and last
    name_parts = real_name.split()
    real_first = name_parts[0]
    real_last = name_parts[-1]
    
    # Check if components of real name appear in alternate names
    for alt_name in alternate_names:
        if real_first.lower() in alt_name.lower() and real_last.lower() in alt_name.lower():
            # We found the real name in alternate names, format with pen name
            return f"{real_first} '{pen_name}' {real_last}"
    
    return real_name

def _handle_book_confirmation(request):
    """Process the confirmed book selection and create local records"""
    # Add debug logging for the full request context
    logger.info("=== Book Confirmation Request Details ===")
    logger.info("Session data: %s", dict(request.session))
    logger.info("POST data: %s", dict(request.POST))
    logger.info("GET data: %s", dict(request.GET))
    
    # Initialize authors list at the start
    authors = []
    editors = []
    
    # Add detailed POST data logging
    logger.info("Raw POST data:")
    for key, value in request.POST.items():
        logger.info("  %s: %s", key, value)

    # Check if we're creating a collection
    if 'collection_first_work' in request.session:
        return _handle_collection_confirmation(request)
        
    # Add logging at the start
    logger.info("Processing book confirmation with POST data:")
    logger.info("is_multivolume: %s", request.POST.get('is_multivolume'))
    logger.info("entry_type: %s", request.POST.get('entry_type'))
    logger.info("volume_number: %s", request.POST.get('volume_number'))
    logger.info("volume_count: %s", request.POST.get('volume_count'))
    logger.info("display_title: %s", request.POST.get('title'))
    logger.info("author_olid: %s", request.POST.get('author_olid'))
    logger.info("author_name: %s", request.POST.get('author_name'))
    
    action = request.POST.get('action', 'Confirm Without Shelving')
    
    # Get author names and OLIDs from the form
    author_names = request.POST.get('author_names', '').split(',')
    author_olids = request.POST.get('author_olids', '').split(',')
    author_olids = [olid for olid in author_olids if olid]  # Filter empty strings

    # Parse author roles from POST data
    try:
        author_roles = json.loads(request.POST.get('author_roles', '{}'))
    except json.JSONDecodeError:
        author_roles = {}

    # First check for selected author from form or session
    selected_author = None
    selected_olid = request.POST.get('selected_author_olid') or request.session.get('selected_author_olid')
    if selected_olid:
        selected_author = Author.objects.filter(olid=selected_olid).first()
        logger.info("Found selected author: %s", selected_author)

    # Get the work details from OpenLibrary
    work_data = None
    if request.POST.get('work_olid'):
        ol = CachedOpenLibrary()
        try:
            work_data = ol.Work.get(request.POST.get('work_olid'))
            logger.info("Found OpenLibrary work: %s", work_data)
        except Exception as e:
            logger.warning(f"Error getting work details from OpenLibrary: {e}")

    # If we don't have author OLIDs but have work data, try to match authors
    if not author_olids and work_data:
        # First try to match by OLID from work authors
        if hasattr(work_data, 'authors'):
            for work_author in work_data.authors:
                if hasattr(work_author, 'key'):
                    author_olid = str(work_author.key).split('/')[-1]
                    if author_olid:
                        # Check if this OLID matches any local author
                        local_author = Author.objects.filter(olid=author_olid).first()
                        if local_author:
                            selected_author = local_author
                            logger.info("Found matching local author by OLID: %s", local_author)
                            author_olids.append(author_olid)

        # If still no match and we have alternate names, try matching those
        if not selected_author and hasattr(work_data, 'author_alternative_name'):
            alt_names = work_data.author_alternative_name
            for local_author in Author.objects.all():
                if local_author.search_name in [name.lower() for name in alt_names]:
                    selected_author = local_author
                    logger.info("Found matching local author by alternate name: %s", local_author)
                    if local_author.olid:
                        author_olids.append(local_author.olid)
                    break

    # Get the work_olid from the POST data
    work_olid = request.POST.get('work_olid')
    if not work_olid:
        return HttpResponseBadRequest('work_olid required')

    # Get OpenLibrary work data for alternate names
    ol = CachedOpenLibrary()
    try:
        work = ol.Work.get(work_olid)
        if work:
            logger.info("Found OpenLibrary work: %s", work)
            # Update authors with alternate names if we find them
            if hasattr(work, 'author_alternative_name'):
                for olid in author_olids:
                    local_author = Author.objects.filter(olid=olid).first()
                    if local_author:
                        if not local_author.alternate_names:
                            local_author.alternate_names = []
                        for alt_name in work.author_alternative_name:
                            if alt_name not in local_author.alternate_names:
                                local_author.alternate_names.append(alt_name)
                        local_author.save()
                        logger.info("Updated author %s with alternate names: %s", 
                                  local_author.primary_name, local_author.alternate_names)
    except Exception as e:
        logger.warning("Error getting work details from OpenLibrary: %s", e)

    # Check if Work already exists and has copies
    existing_work = Work.objects.filter(olid=work_olid).first()
    if existing_work and existing_work.edition_set.filter(copy__isnull=False).exists():
        if request.POST.get('confirm_duplicate') != 'true':
            context = {
                'work': existing_work,
                'form_data': request.POST,
                'locations': Location.objects.all()
            }
            return render(request, 'confirm-duplicate.html', context)
        
    # Get the user's submitted title from POST
    display_title = request.POST.get('title')
    # Strip any volume number from the title
    clean_title = Work.strip_volume_number(display_title)
    publisher = request.POST.get('publisher')
    
    # Use the user's submitted title for search_name too
    search_name = clean_title.lower()

    # Handle multi-volume works
    is_multivolume = request.POST.get('is_multivolume') == 'on'
    entry_type = request.POST.get('entry_type')
    volume_number = request.POST.get('volume_number')
    volume_count = request.POST.get('volume_count')
    
    # Process author OLIDs
    final_author_olids = []
    for olid in author_olids:
        logger.info("Processing OLID: %s", olid)
        # If we have a selected author, use that instead of searching
        if selected_author:
            author = selected_author
            # Get the OpenLibrary details to update the author
            ol = CachedOpenLibrary()
            try:
                author_details = ol.Author.get(olid)
                if author_details:
                    alternate_names = author_details.get('alternate_names', [])
                    real_name = author_details.get('personal_name') or author_details.get('name')
                    if real_name:
                        formatted_name = _format_pen_name(
                            real_name=real_name,
                            pen_name=author.search_name.title(),
                            alternate_names=alternate_names
                        )
                        author.primary_name = formatted_name
                        author.alternate_names = alternate_names
                        author.save()
            except Exception as e:
                logger.warning(f"Error getting author details from OpenLibrary: {e}")
        else:
            # Original author matching logic...
            author = Author.objects.filter(olid=olid).first()
            if not author:
                logger.info("No direct OLID match, trying name matching")
                # Try to match by name if we have a local author
                local_authors = Author.objects.all()
                for local_author in local_authors:
                    logger.info("Checking local author: %s (search_name: %s)", 
                              local_author.primary_name, local_author.search_name)
                    # Get the OpenLibrary details for this author
                    ol = CachedOpenLibrary()
                    try:
                        author_details = ol.Author.get(olid)
                        if author_details:
                            alternate_names = author_details.get('alternate_names', [])
                            logger.info("Found OL author details: %s", author_details)
                            logger.info("Alternate names: %s", alternate_names)
                            # Check if our local author's name appears in alternate names
                            local_name = local_author.search_name.lower()
                            alt_names_lower = [name.lower() for name in alternate_names]
                            logger.info("Checking if %s appears in %s", local_name, alt_names_lower)
                            if local_name in alt_names_lower or any(local_name in alt.lower() for alt in alternate_names):
                                logger.info("Found name match!")
                                # This is the same author with a different OLID
                                real_name = author_details.get('personal_name') or author_details.get('name')
                                if real_name:
                                    logger.info("Formatting name with real_name: %s, pen_name: %s", 
                                              real_name, local_author.search_name.title())
                                    # Format name with pen name
                                    formatted_name = _format_pen_name(
                                        real_name=real_name,
                                        pen_name=local_author.search_name.title(),
                                        alternate_names=alternate_names
                                    )
                                    logger.info("Formatted name: %s", formatted_name)
                                    # Update author with new OLID and name format
                                    local_author.olid = olid
                                    local_author.primary_name = formatted_name
                                    local_author.alternate_names = alternate_names
                                    local_author.save()
                                    author = local_author
                                    break
                    except Exception as e:
                        logger.warning(f"Error getting author details from OpenLibrary: {e}")
                        continue

        if author:
            final_author_olids.append(olid)
        else:
            # If still no match, create new author
            for name in author_names:
                if author_roles.get(name) == "AUTHOR":
                    logger.info("Creating new author with name: %s", name)
                    author = Author.objects.create(
                        primary_name=name,
                        search_name=name.lower(),
                        olid=olid
                    )
                    final_author_olids.append(olid)
                    break

    # For any remaining names without matched OLIDs, try name matching
    for name in author_names:
        name = name.strip()
        if not name:
            continue
            
        # Check if we have a local author match
        local_authors = Author.objects.all()
        for local_author in local_authors:
            if _author_name_matches(name, local_author, {'author_alternative_name': []}):
                if local_author.olid not in final_author_olids:
                    final_author_olids.append(local_author.olid)
                break
        
        # If still no match and we have work info with matching name, use that author's OLID
        if not final_author_olids and existing_work and hasattr(existing_work, 'authors'):
            for work_author in existing_work.authors:
                if hasattr(work_author, 'key'):
                    work_author_olid = str(work_author.key).split('/')[-1]
                    if work_author_olid:
                        final_author_olids.append(work_author_olid)
                        break
            
        # If still no match, create new author
        if not final_author_olids and author_roles.get(name) == "AUTHOR":
            new_author = Author.objects.create(
                primary_name=name,
                search_name=name.lower()
            )
            final_author_olids.append(new_author.olid)

    logger.info("Final author_olids list: %s", final_author_olids)
    
    # Get authors and editors before any work creation
    for olid in final_author_olids:
        try:
            author = Author.objects.get(olid=olid)
            if author_roles.get(author.primary_name, 'AUTHOR') == 'AUTHOR':
                authors.append(author)
            else:
                editors.append(author)
        except Author.DoesNotExist:
            logger.warning(f"No matching author found for OLID: {olid}")
            continue

    # Track if this is a new work for the message
    is_new_work = False
    
    # Handle work creation
    work_qs = Work.objects.filter(olid=work_olid)
    if not work_qs:
        is_new_work = True
        
        # Convert empty strings to None for numeric fields
        volume_number_val = None if volume_number == '' else volume_number
        
        work = Work.objects.create(
            olid=work_olid,
            title=clean_title,
            search_name=search_name,
            type='NOVEL',
            is_multivolume=is_multivolume,
            volume_number=volume_number_val
        )
        
        # Add authors and editors
        for olid in final_author_olids:
            try:
                author = Author.objects.get(olid=olid)
                if author_roles.get(author.primary_name, 'AUTHOR') == 'AUTHOR':
                    work.authors.add(author)
                else:
                    work.editors.add(author)
            except Author.DoesNotExist:
                # Try looking up by name instead
                author_name = next((name for name in author_names if name in author_roles), None)
                if author_name:
                    try:
                        author = Author.objects.get(primary_name=author_name)
                        if author_roles.get(author_name, 'AUTHOR') == 'AUTHOR':
                            work.authors.add(author)
                        else:
                            work.editors.add(author)
                    except Author.DoesNotExist:
                        logger.warning(f"No matching author found for name: {author_name}")
                        continue
        
        # Verify the additions
        work.refresh_from_db()
        logger.info("Work authors: %s", [a.primary_name for a in work.authors.all()])
        logger.info("Work editors: %s", [e.primary_name for e in work.editors.all()])

        logger.info("Added new Work %s (%s) AKA %s with %d authors/editors", 
                   clean_title, work_olid, search_name, len(final_author_olids))
    else:
        work = work_qs[0]

    # Handle multivolume specifics if needed
    if is_multivolume:
        # Get authors and editors before creating volumes
        authors = []
        editors = []
        for olid in final_author_olids:
            author = Author.objects.get(olid=olid)
            if author_roles.get(author.primary_name, 'AUTHOR') == 'AUTHOR':
                authors.append(author)
            else:
                editors.append(author)

        if entry_type == 'COMPLETE':
            work, volumes = Work.create_volume_set(
                title=clean_title,
                volume_count=int(volume_count),
                authors=authors,
                editors=editors,
                olid=work_olid,
                search_name=search_name,
                type='NOVEL'
            )
        elif entry_type == 'SINGLE':
            work, volume = Work.create_single_volume(
                set_title=clean_title,
                volume_number=int(volume_number) if volume_number else 1,
                authors=authors,
                editors=editors,
                olid=work_olid,
                search_name=search_name,
                type='NOVEL'
            )
            volumes = [volume]
        elif entry_type == 'PARTIAL':
            volume_numbers = [int(v) for v in request.POST.get('volume_numbers', '').split(',') if v]
            work, volumes = Work.create_partial_volume_set(
                title=clean_title,
                volume_numbers=volume_numbers,
                authors=authors,
                editors=editors,
                olid=work_olid,
                search_name=search_name,
                type='NOVEL'
            )

        # Create Editions and Copies for all volumes
        for volume in volumes:
            edition = Edition.objects.create(
                work=volume,
                publisher=publisher if publisher else "Unknown",
                format="PAPERBACK",
            )

            copy_data = {
                'edition': edition,
                'condition': "GOOD",
            }

            if action == 'Confirm and Shelve':
                shelf_id = request.POST.get('shelf')
                if shelf_id:
                    shelf = Shelf.objects.get(id=shelf_id)
                    copy_data.update({
                        'shelf': shelf,
                        'location': shelf.bookcase.get_location(),
                        'room': shelf.bookcase.room,
                        'bookcase': shelf.bookcase
                    })

            Copy.objects.create(**copy_data)
        
        # Add message after creating all volumes
        if action == 'Confirm and Shelve' and shelf_id:
            location_path = f"{shelf.bookcase.get_location().name} > {shelf.bookcase.room.name} > {shelf.bookcase.name} > Shelf {shelf.position}"
            message = f"new_copy_shelved&title={urllib.parse.quote(display_title)}&location={urllib.parse.quote(location_path)}"
        else:
            message = f"new_work&title={urllib.parse.quote(display_title)}"
    else:
        # Original single-volume Edition/Copy creation code
        edition = Edition.objects.create(
            work=work,
            publisher=publisher if publisher else "Unknown",
            format="PAPERBACK",
        )

        # Create a Copy with optional shelf assignment
        copy_data = {
            'edition': edition,
            'condition': "GOOD",
        }

        if action == 'Confirm and Shelve':
            shelf_id = request.POST.get('shelf')
            if shelf_id:
                shelf = Shelf.objects.get(id=shelf_id)
                copy_data.update({
                    'shelf': shelf,
                    'location': shelf.bookcase.get_location(),
                    'room': shelf.bookcase.room,
                    'bookcase': shelf.bookcase
                })

        copy = Copy.objects.create(**copy_data)

        # Add appropriate message based on shelving status
        if action == 'Confirm and Shelve' and shelf_id:
            location_path = f"{shelf.bookcase.get_location().name} > {shelf.bookcase.room.name} > {shelf.bookcase.name} > Shelf {shelf.position}"
            message = f"new_copy_shelved&title={urllib.parse.quote(display_title)}&location={urllib.parse.quote(location_path)}"
        else:
            message = f"new_work&title={urllib.parse.quote(display_title)}"

    # Add logging for author matching
    logger.info("=== Author Matching ===")
    logger.info("Authors found: %s", [a.primary_name for a in authors])
    logger.info("Editors found: %s", [e.primary_name for e in editors])

    # Add logging before work creation
    logger.info("=== Work Creation ===")
    logger.info("Creating work with title: %s", clean_title)
    logger.info("Work OLID: %s", work_olid)
    logger.info("Authors to associate: %s", authors)

    return HttpResponseRedirect(f'/author/?message={message}')

def _handle_book_search(request):
    """Search for and display potential book matches"""
    logger.info("=== Collection Context at Start of Book Search ===")
    logger.info("GET params first_work data: %s", {
        k: v for k, v in request.GET.items() if k.startswith('first_work_')
    })
    logger.info("POST params first_work data: %s", {
        k: v for k, v in request.POST.items() if k.startswith('first_work_')
    })

    ol = CachedOpenLibrary()
    
    # Initialize form_args
    form_args = {}
    
    # Get search parameters
    params = request.GET
    if 'title' not in params:
        return HttpResponseBadRequest('Title required')
    
    search_title = params['title']
    
    # Build author context and get local author if available
    local_author = None
    if 'author_name' in params:
        form_args['author_name'] = params['author_name']
    if 'author_olid' in params:
        form_args['author_olid'] = params['author_olid']
        local_author = Author.objects.filter(olid=form_args['author_olid']).first()
        logger.info("Found local author: %s with OLID %s", 
                   local_author.primary_name if local_author else None, 
                   form_args['author_olid'])
    
    context = {'title_url': "title.html?" + urllib.parse.urlencode(form_args)}

    # Get first work data from GET or POST params
    first_work_data = {}
    for key in ['first_work_title', 'first_work_olid', 'first_work_author_names', 
               'first_work_author_olids', 'first_work_publisher']:
        if value := request.GET.get(key) or request.POST.get(key):
            first_work_data[key] = value

    # Determine if we're in collection mode and set template accordingly
    if first_work_data:
        logger.info("=== Collection Mode Detected ===")
        logger.info("First work details: %s", first_work_data)
        context['first_work'] = first_work_data
        template = 'confirm-collection.html'
    else:
        template = 'confirm-book.html'

    # Handle local autocomplete results
    if DIVIDER in search_title:
        title, olid = search_title.split(DIVIDER)
        form_args['title'] = title
        form_args['work_olid'] = olid
        
        # Check for existing work with copies
        existing_work = Work.objects.filter(olid=olid).first()
        if existing_work and existing_work.edition_set.filter(copy__isnull=False).exists():
            context = {
                'work': existing_work,
                'form_data': form_args,
                'locations': Location.objects.all()
            }
            return render(request, 'confirm-duplicate.html', context)
            
        context['form'] = ConfirmBook(form_args)
        return HttpResponseRedirect('/author')

    # Search OpenLibrary and build forms
    results = _search_openlibrary(ol, search_title, form_args.get('author_olid'), form_args.get('author_name'))
    
    # Build forms for results
    forms = []
    for result in results:
        display_title = result.title
        work_olid = result.identifiers['olid'][0]
        
        # Check for existing work with copies
        existing_work = Work.objects.filter(olid=work_olid).first()
        if existing_work and existing_work.edition_set.filter(copy__isnull=False).exists():
            context = {
                'work': existing_work,
                'form_data': {
                    'title': display_title,
                    'work_olid': work_olid,
                    'author_names': result.authors[0]['name'] if result.authors else '',
                    'author_olids': result.authors[0].get('olid', '') if result.authors else ''
                },
                'locations': Location.objects.all()
            }
            return render(request, 'confirm-duplicate.html', context)
        
        # Process author information
        author_names = []
        author_olids = []
        
        if result.authors:
            logger.info("Raw author data from result: %s", result.authors)
            for author in result.authors:
                logger.info("Processing author: %s", author)
                author_name = author['name']
                
                # Convert result to dict for author name matching
                result_dict = _work_to_dict(result)
                
                # If we have a local author or author_olid from args, use that OLID
                if local_author and _author_name_matches(author_name, local_author, result_dict):
                    author_olid = local_author.olid
                    # Update the author name to match our local author
                    author_name = local_author.primary_name
                elif form_args.get('author_olid') and author_name == form_args.get('author_name', '').split(' (')[0]:
                    author_olid = form_args['author_olid']
                else:
                    # Get author OLID from author_key if available
                    ol_author_id = None
                    if isinstance(author.get('author_key'), list) and author['author_key']:
                        ol_author_id = author['author_key'][0]
                    elif isinstance(author.get('key'), str):
                        ol_author_id = author['key'].replace('/authors/', '')
                    author_olid = author.get('olid', ol_author_id)
                
                logger.info("Using author_olid: %s for author: %s", author_olid, author_name)
                
                author_names.append(author_name)
                if author_olid:  # Only append if we actually have an OLID
                    author_olids.append(author_olid)
                    logger.info("Added author: name=%s, olid=%s", author_name, author_olid)
                else:
                    logger.warning("No OLID found for author: %s", author_name)

        # Update form_args BEFORE creating the form
        form_args.update({
            'title': result.title,
            'work_olid': result.identifiers['olid'][0],
            'author_names': ','.join(author_names),
            'author_olids': ','.join(author_olids)
        })

        # If this is the first result and we're in collection mode, add it as second_work
        if first_work_data:
            logger.info("=== Adding Second Work to Collection ===")
            logger.info("First work from params: %s", first_work_data)
            second_work = {
                'title': result.title,
                'work_olid': result.identifiers['olid'][0],
                'author_names': result.authors[0]['name'] if result.authors else '',
                'author_olids': ','.join(author_olids),
                'publisher': result.publisher[0] if hasattr(result, 'publisher') and result.publisher else 'Unknown'
            }
            logger.info("Second work details: %s", second_work)
            context['second_work'] = second_work
            
            # Add first work data to form_args
            logger.info("=== Adding First Work Data to Form Args ===")
            logger.info("First work data before update: %s", first_work_data)
            logger.info("Form args before update: %s", form_args)
            form_args.update({
                'first_work_title': first_work_data['first_work_title'],
                'first_work_olid': first_work_data['first_work_olid'],
                'first_work_author_names': first_work_data['first_work_author_names'],
                'first_work_author_olids': first_work_data['first_work_author_olids']
            })
            logger.info("Form args after update: %s", form_args)

        # Now create the form with the updated form_args
        form = ConfirmBook(form_args)
        logger.info("=== Created Form ===")
        logger.info("Form data: %s", form.data)
        forms.append(form)
        context['form'] = form

    # Add locations to context for the template
    context['locations'] = Location.objects.all()
    context['forms'] = forms
    
    return render(request, template, context)

def _work_to_dict(work):
    """Convert a CachedWork object to a dictionary with the fields we need"""
    # Get alternate names from both the root level and author data
    alt_names = getattr(work, 'author_alternative_name', [])
    
    # Add alternate names from author data if available
    for author in getattr(work, 'authors', []) or []:
        if 'author_alternative_name' in author:
            alt_names.extend(author['author_alternative_name'])

    return {
        'author_alternative_name': alt_names,
        'author_key': getattr(work, 'author_key', []),
        'author_name': getattr(work, 'author_name', []),
        'title': getattr(work, 'title', '')
    }

def _search_openlibrary(ol, title, author_olid=None, author_name=None):
    """Search OpenLibrary for works matching title and author"""
    results = []
    
    # Build author context and get local author if available
    local_author = None
    if author_olid:
        local_author = Author.objects.filter(olid=author_olid).first()
        logger.info("Found local author: %s with OLID %s", 
                   local_author.primary_name if local_author else None, 
                   author_olid)
    
    # Try initial search with author ID if available
    if author_olid:
        logger.info("Searching OpenLibrary with author='%s', title='%s', limit=2", author_olid, title)
        try:
            results = ol.Work.search(author=author_olid, title=title, limit=2)
            # Check author keys in results
            if results and local_author:
                for result in results:
                    if hasattr(result, 'author_key') and result.author_key:
                        ol_author_id = result.author_key[0] if isinstance(result.author_key, list) else result.author_key
                        if ol_author_id and ol_author_id != local_author.olid:
                            logger.info("Found alternate OLID %s for author %s", ol_author_id, local_author.primary_name)
                            if not local_author.alternate_olids:
                                local_author.alternate_olids = []
                            if ol_author_id not in local_author.alternate_olids:
                                local_author.alternate_olids.append(ol_author_id)
                                local_author.save()
        except Exception as e:
            logger.exception("Error during OpenLibrary search")
            raise

    # If no results with ID, try author name
    if not results and author_name:
        try:
            # Strip dates and other parenthetical information before searching
            clean_name = re.sub(r'\s*\([^)]*\)', '', author_name).strip()
            logger.info("Trying search with author name '%s'", clean_name)
            name_results = ol.Work.search(author=clean_name, title=title, limit=2)
            if name_results:
                # Check if any authors match our local author's alternate names
                for result in name_results:
                    if result.authors and local_author:
                        for author in result.authors:
                            if _author_name_matches(author['name'], local_author, result):
                                # Found a match - check for alternate OLID
                                if hasattr(result, 'author_key') and result.author_key:
                                    ol_author_id = result.author_key[0] if isinstance(result.author_key, list) else result.author_key
                                    if ol_author_id and ol_author_id != local_author.olid:
                                        logger.info("Found alternate OLID %s for author %s", ol_author_id, local_author.primary_name)
                                        if not local_author.alternate_olids:
                                            local_author.alternate_olids = []
                                        if ol_author_id not in local_author.alternate_olids:
                                            local_author.alternate_olids.append(ol_author_id)
                                            local_author.save()
                results.extend(name_results)
            
            # If still no results, try with simplified author name (remove middle initial)
            if not results and ' ' in clean_name:
                # Split name and check if we have what looks like a middle initial
                name_parts = clean_name.split()
                if len(name_parts) > 2 and len(name_parts[1]) <= 2:
                    simplified_name = f"{name_parts[0]} {name_parts[-1]}"
                    logger.info("Trying search with simplified author name '%s'", simplified_name)
                    simple_results = ol.Work.search(author=simplified_name, title=title, limit=2)
                    if simple_results:
                        results.extend(simple_results)
                        
            # If still no results, try with last name only
            if not results and ' ' in clean_name:
                # Get the last word as the last name
                last_name = clean_name.split()[-1]
                logger.info("Trying search with author last name only '%s'", last_name)
                try:
                    last_name_results = ol.Work.search(author=last_name, title=title, limit=2)
                    if last_name_results:
                        results.extend(last_name_results)
                except Exception as e:
                    logger.warning("Error during last name search: %s", e)

        except Exception as e:
            logger.warning("Error during author name search: %s", e)

    # If still no results, try title-only search
    if not results:
        logger.info("Trying title-only search for '%s'", title)
        try:
            title_results = ol.Work.search(title=title, limit=2)
            if title_results:
                # Check if any authors match our local author's alternate names
                for result in title_results:
                    if result.authors and local_author:
                        result_dict = _work_to_dict(result)
                        for author in result.authors:
                            if _author_name_matches(author['name'], local_author, result_dict):
                                # Found a match - check for alternate OLID
                                if hasattr(result, 'author_key') and result.author_key:
                                    ol_author_id = result.author_key[0] if isinstance(result.author_key, list) else result.author_key
                                    if ol_author_id and ol_author_id != local_author.olid:
                                        logger.info("Found alternate OLID %s for author %s", ol_author_id, local_author.primary_name)
                                        if not local_author.alternate_olids:
                                            local_author.alternate_olids = []
                                        if ol_author_id not in local_author.alternate_olids:
                                            local_author.alternate_olids.append(ol_author_id)
                                            local_author.save()
                results.extend(title_results)
        except Exception as e:
            logger.warning("Error during title-only search: %s", e)
            if not results:
                raise Exception("no result")

    return results[:2]  # Keep only first two results

def title_only_search(request):
    """Search for a book by title only"""
    if request.method == 'GET':
        form = TitleOnlyForm()
        return render(request, 'title-only.html', {'form': form})
    
    if request.method == 'POST':
        form = TitleOnlyForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            return _handle_title_only_search(request, title)
    
    return HttpResponseBadRequest('Invalid request')

def _handle_title_only_search(request, title):
    """Process title-only search and display results"""
    ol = CachedOpenLibrary()
    try:
        # Search OpenLibrary with title only
        results = ol.Work.search(title=title, limit=5)
        
        # Build forms for results
        forms = []
        for result in results:
            display_title = result.title
            work_olid = result.identifiers['olid'][0]
            
            # Check for existing work
            existing_work = Work.objects.filter(olid=work_olid).first()
            if existing_work and existing_work.edition_set.filter(copy__isnull=False).exists():
                context = {
                    'work': existing_work,
                    'form_data': {
                        'title': display_title,
                        'work_olid': work_olid,
                        'author_names': result.authors[0]['name'] if result.authors else '',
                        'author_olids': result.authors[0].get('olid', '') if result.authors else ''
                    },
                    'locations': Location.objects.all()
                }
                return render(request, 'confirm-duplicate.html', context)
            
            # Create form for this result
            form_args = {
                'title': display_title,
                'work_olid': work_olid,
                'author_names': ', '.join(a['name'] for a in result.authors) if result.authors else '',
                'author_olids': ','.join(a.get('olid', '') for a in result.authors) if result.authors else ''
            }
            
            forms.append(ConfirmBook(form_args))
        
        context = {
            'forms': forms,
            'locations': Location.objects.all(),
            'title_url': 'title-only.html'
        }
        return render(request, 'confirm-book.html', context)
        
    except Exception as e:
        logger.exception("Error during title-only search")
        context = {
            'error': str(e),
            'form': TitleOnlyForm(initial={'title': title})
        }
        return render(request, 'title-only.html', context)

def start_collection(request):
    """Begin collection creation flow by rendering author page with first work context"""
    logger.info("=== Starting Collection Creation ===")
    logger.info("POST data for first work: %s", dict(request.POST))
    
    # Create form context with first work's details - using the field names from the POST data
    initial_data = {
        'first_work_title': request.POST.get('first_work_title'),  # These match the names in the POST data
        'first_work_olid': request.POST.get('first_work_olid'),
        'first_work_author_names': request.POST.get('first_work_author_names'),
        'first_work_author_olids': request.POST.get('first_work_author_olids'),
        'first_work_publisher': request.POST.get('first_work_publisher')
    }
    
    logger.info("Created initial data for collection: %s", initial_data)
    
    form = AuthorForm()
    # Add hidden fields to form for collection data
    for key, value in initial_data.items():
        form.fields[key] = forms.CharField(widget=forms.HiddenInput(), initial=value)
        logger.info("Added hidden field %s with value %s", key, value)
    
    return render(request, 'author.html', {
        'form': form,
        'author_role': 'AUTHOR',
        'collection_data': initial_data  # Pass to template for display
    })

def cancel_collection(request):
    """Cancel collection creation and clear session data"""
    if 'collection_first_work' in request.session:
        del request.session['collection_first_work']
    return HttpResponseRedirect('/author/')

def _handle_collection_confirmation(request):
    """Handle the confirmation of a second work to create a collection"""
    # Add detailed logging of all form fields
    logger.info("Raw POST data:")
    for key, value in request.POST.items():
        logger.info("  %s: %s", key, value)
    
    # Add logging at the start
    logger.info("Processing collection confirmation with POST data:")
    logger.info("First work from session: %s", request.session['collection_first_work'])
    logger.info("Second work title: %s", request.POST.get('second_work_title'))
    logger.info("Second work OLID: %s", request.POST.get('second_work_olid'))
    logger.info("Second work author names: %s", request.POST.get('second_work_author_names'))
    logger.info("Second work author OLIDs: %s", request.POST.get('second_work_author_olids'))
    logger.info("Second work publisher: %s", request.POST.get('publisher'))
    logger.info("Action: %s", request.POST.get('action'))
    logger.info("Shelf ID: %s", request.POST.get('shelf'))
    
    # Get the first work's details from session
    first_work = request.session['collection_first_work']
    
    # Get the second work's details from POST
    second_work = {
        'title': request.POST.get('second_work_title'),
        'work_olid': request.POST.get('second_work_olid'),
        'author_names': request.POST.get('second_work_author_names'),
        'author_olids': request.POST.get('second_work_author_olids'),
        'publisher': request.POST.get('publisher'),
    }
    
    # Create the collection work
    collection_title = request.POST.get('title')
    collection = Work.objects.create(
        title=collection_title,
        search_name=collection_title,
        type='COLLECTION'
    )
    
    # Create and link the component works
    works_to_create = [first_work, second_work]
    contained_works = []
    all_authors = set()  # Track all authors for the collection
    
    for work_data in works_to_create:
        logger.info("Processing work data: %s", work_data)
        # Create or get the component work
        work = Work.objects.filter(olid=work_data['work_olid']).first()
        if not work:
            work = Work.objects.create(
                olid=work_data['work_olid'],
                title=work_data['title'],
                search_name=work_data['title'],
                type='NOVEL'
            )
            
            # Add authors
            if work_data['author_olids']:  # Check if we have author OLIDs
                for olid, name in zip(work_data['author_olids'].split(','), 
                                    work_data['author_names'].split(',')):
                    if olid:
                        author = Author.objects.get_or_fetch(olid)
                        if author:
                            work.authors.add(author)
                            all_authors.add(author)  # Add to collection authors set
        else:
            # If work already exists, still collect its authors
            all_authors.update(work.authors.all())
        
        # Add to our list of contained works
        contained_works.append(work)
    
    # Add all collected authors to the collection
    for author in all_authors:
        collection.authors.add(author)
    
    # Link both works to the collection
    for work in contained_works:
        collection.component_works.add(work)

    # Create edition and copy
    edition = Edition.objects.create(
        work=collection,
        publisher="Various" if first_work['publisher'] != second_work['publisher'] else first_work['publisher'],
        format="PAPERBACK"
    )
    
    # Handle shelving if requested
    copy_data = {
        'edition': edition,
        'condition': "GOOD"
    }
    
    action = request.POST.get('action', 'Confirm Without Shelving')
    if action == 'Confirm and Shelve':
        shelf_id = request.POST.get('shelf')
        if shelf_id:
            shelf = Shelf.objects.get(id=shelf_id)
            copy_data.update({
                'shelf': shelf,
                'location': shelf.bookcase.get_location(),
                'room': shelf.bookcase.room,
                'bookcase': shelf.bookcase
            })
    
    Copy.objects.create(**copy_data)
    
    # Clear the session data
    del request.session['collection_first_work']
    
    # Create appropriate message
    if action == 'Confirm and Shelve' and shelf_id:
        location_path = f"{shelf.bookcase.get_location().name} > {shelf.bookcase.room.name} > {shelf.bookcase.name} > Shelf {shelf.position}"
        message = f"new_copy_shelved&title={urllib.parse.quote(collection_title)}&location={urllib.parse.quote(location_path)}"
    else:
        message = f"new_work&title={urllib.parse.quote(collection_title)}"
    
    return HttpResponseRedirect(f'/author/?message={message}')

def _author_name_matches(name, local_author, result):
    """Check if an author name matches a local author, including alternate names"""
    # Normalize names for comparison
    name = name.lower()
    local_name = local_author.primary_name.lower()
    
    # Direct match
    if name == local_name:
        return True
        
    # Check result's alternate names against local primary name
    alt_names = []
    if isinstance(result, dict):  # Handle both dict and OpenLibrary result objects
        if 'author_alternative_name' in result:
            alt_names.extend(result['author_alternative_name'])
        elif 'author_alternative_names' in result:  # Handle possible alternate key
            alt_names.extend(result['author_alternative_names'])
    
    alt_names = [alt.lower() for alt in alt_names]
    if local_name in alt_names:
        return True
            
    # Check local alternate names against result name
    if local_author.alternate_names:
        local_alts = [alt.lower() for alt in local_author.alternate_names]
        if name in local_alts:
            return True

    # Check if the OpenLibrary author has the same OLID
    if isinstance(result, dict):
        ol_author_id = None
        if isinstance(result.get('author_key'), list) and result['author_key']:
            ol_author_id = result['author_key'][0]
        elif isinstance(result.get('key'), str):
            ol_author_id = result['key'].replace('/authors/', '')
        
        if ol_author_id and ol_author_id == local_author.olid:
            return True
            
    return False
