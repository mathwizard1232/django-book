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
    logger.info("GET params data: %s", {
        k: v for k, v in request.GET.items()
    })
    logger.info("POST params data: %s", {
        k: v for k, v in request.POST.items()
    })

    if request.method == 'POST':
        return WorkController(request).handle_book_confirmation()  # Try new controller
    else:
        return _handle_book_search(request)

def _format_pen_name(real_name, pen_name, alternate_names, force_format=False):
    """Format author name to include pen name if appropriate.
    
    Args:
        real_name (str): The author's real name (e.g., "Frederick Schiller Faust")
        pen_name (str): The author's pen name (e.g., "Max Brand")
        alternate_names (list): List of alternate names to check against
        force_format (bool): If True, always format with pen name regardless of alternate names
        
    Returns:
        str: Formatted name with pen name in quotes if appropriate, or original name
    """
    # If real_name and pen_name are the same, just return the name
    if real_name.lower() == pen_name.lower():
        return real_name

    # Split names into components and just use first and last
    name_parts = real_name.split()
    real_first = name_parts[0]
    real_last = name_parts[-1]
    
    # Check if we should force format or if components of real name appear in alternate names
    if force_format or any(real_first.lower() in alt_name.lower() and real_last.lower() in alt_name.lower() 
                          for alt_name in alternate_names):
        # Format with pen name
        return f"{real_first} '{pen_name}' {real_last}"
    
    return real_name

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
    
    # Get search parameters from GET or POST
    params = request.GET.copy()
    params.update(request.POST)
    
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
        
        # Create author if we have an OLID but no local author
        if not local_author:
            # Fetch full author details from OpenLibrary
            ol = CachedOpenLibrary()
            author_details = ol.Author.get(form_args['author_olid'])
            logger.info("Creating author from details: %s", author_details)
            
            # Get the search term if available
            search_term = params.get('search_term') or author_details.get('name')  # hacky fallback to use author name as search term
            # this lets us recognize the case where we've dropped the search term because it matched the name
            real_name = author_details.get('personal_name') or author_details.get('name')
            
            logger.info("`get_title` Search term: %s", search_term)
            logger.info("`get_title` Real name: %s", real_name)
            logger.info("`get_title` Author name: %s", author_details.get('name'))
            # alternate names
            logger.info("`get_title` Alternate names: %s", author_details.get('alternate_names', []))
            # If search term matches an alternate name, format with pen name
            if search_term and (search_term in author_details.get('alternate_names', []) or 
                                    (search_term == author_details.get('name')
                                     and search_term != real_name)):
                logger.info("`get_title` Formatting with pen name")
                primary_name = f"{real_name.split()[0]} '{search_term}' {real_name.split()[-1]}"
            else:
                primary_name = real_name
            
            # Create author with complete information
            local_author = Author.objects.create(
                olid=form_args['author_olid'],
                primary_name=primary_name,
                search_name=(search_term or real_name).lower(),
                birth_date=author_details.get('birth_date'),
                death_date=author_details.get('death_date'),
                alternate_names=author_details.get('alternate_names', [])
            )
            logger.info("Created author: %s", local_author.primary_name)
    
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
            logger.info("Full result data: %s", vars(result))
            for author in result.authors:
                logger.info("Processing author: %s", author)
                author_name = author['name']
                
                # If this is our local author by OLID, use their name
                if local_author and author.get('key', '').endswith(local_author.olid):
                    logger.info("Using local author name %s instead of %s (matched by OLID)", 
                              local_author.primary_name, author_name)
                    author_name = local_author.primary_name
                
                # If we have a name mismatch with the search author, try to fetch full details
                if form_args.get('author_name') and author_name != form_args['author_name']:
                    logger.info("Name mismatch - search: %s, result: %s", form_args['author_name'], author_name)
                    # Try to get full author details using the work's author OLID
                    if 'olid' in author:
                        try:
                            author_details = ol.Author.get(author['olid'])
                            logger.info("Found work author details: %s", author_details)
                            # Add these details to our result for name matching
                            result_dict = {
                                'author_alternative_name': author_details.get('alternate_names', []),
                                'author_key': [author['olid']],
                                'author_name': [author_name],
                            }
                            if _author_name_matches(author_name, local_author, result_dict):
                                logger.info("Found matching author through alternate names")
                                # Initialize alternate_olids if needed
                                if not local_author.alternate_olids:
                                    local_author.alternate_olids = []
                                
                                # Format combined name
                                real_name = author_details.get('personal_name') or author_details.get('name')
                                search_term = request.GET.get('search_term')
                                pen_name = search_term.title() if search_term else local_author.search_name.title()

                                logger.info("=== Pen Name Formatting ===")
                                logger.info("Search term from request: %s", search_term)
                                logger.info("Real name: %s", real_name)
                                logger.info("Pen name being used: %s", pen_name)
                                logger.info("Local author search name: %s", local_author.search_name)
                                logger.info("Author details: %s", author_details)
                                logger.info("olid: %s", author['olid'])

                                if author['olid'] != local_author.olid:
                                    if author['olid'] not in local_author.alternate_olids:
                                        logger.info("Adding alternate OLID: %s", author['olid'])
                                        local_author.alternate_olids.append(author['olid'])
                                        local_author.save()

                                # Only force pen name format if real name is different from pen name
                                force_format = real_name.lower() != pen_name.lower()

                                formatted_name = _format_pen_name(
                                    real_name=real_name,
                                    pen_name=pen_name,
                                    alternate_names=author_details.get('alternate_names', []),
                                    force_format=force_format  # Only force format if names are different
                                )
                                logger.info("Formatted result: %s", formatted_name)
                                
                                # Update names
                                local_author.primary_name = formatted_name
                                # Keep the pen name as search name
                                logger.info("Setting search name to pen name: %s", pen_name)
                                local_author.search_name = pen_name.lower()
                                
                                # Get work counts from OpenLibrary for both authors
                                new_work_count = author_details.get('work_count', 0)
                                try:
                                    current_author_details = ol.Author.get(local_author.olid)
                                    current_work_count = current_author_details.get('work_count', 0)
                                except Exception as e:
                                    logger.warning("Error getting current author details: %s", e)
                                    current_work_count = 0
                                    
                                logger.info("Work counts - new author: %d, current author: %d", 
                                          new_work_count, current_work_count)
                                
                                # If new author has significantly more works, merge additional details
                                if new_work_count > current_work_count * 10:
                                    logger.info("New author has significantly more works - merging")
                                    
                                    # Store old OLID as alternate
                                    if not local_author.alternate_olids:
                                        local_author.alternate_olids = []
                                    local_author.alternate_olids.append(local_author.olid)
                                    
                                    # Update primary OLID
                                    local_author.olid = author['olid']
                                    
                                    # Update biographical details
                                    local_author.birth_date = author_details.get('birth_date')
                                    local_author.death_date = author_details.get('death_date')
                                    
                                    # Update alternate names
                                    if not local_author.alternate_names:
                                        local_author.alternate_names = []
                                    local_author.alternate_names.extend(author_details.get('alternate_names', []))
                                
                                local_author.save()
                                logger.info("Updated author details - primary: %s, search: %s, alternates: %s",
                                          local_author.primary_name, local_author.search_name, 
                                          local_author.alternate_names)
                                
                                author_name = local_author.primary_name
                                author_olid = local_author.olid
                        except Exception as e:
                            logger.warning("Error getting work author details: %s", e)
                
                # Convert result to dict for author name matching
                result_dict = _work_to_dict(result)
                
                # If we have a local author or author_olid from args, use that OLID
                if local_author and _author_name_matches(author_name, local_author, result_dict):
                    author_olid = local_author.olid
                    # Update the author name to match our local author
                    author_name = local_author.primary_name
                    logger.info("Matched local author by name - using primary name: %s, olid: %s", author_name, author_olid)
                elif form_args.get('author_olid') and author_name == form_args.get('author_name', '').split(' (')[0]:
                    author_olid = form_args['author_olid']
                    # Also use the local author's primary name here
                    local_author = Author.objects.filter(olid=author_olid).first()
                    if local_author:
                        author_name = local_author.primary_name
                        logger.info("Matched local author by OLID - using primary name: %s, olid: %s", author_name, author_olid)
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

        # Create new form_args for this specific result
        result_form_args = form_args.copy()  # Make a copy of the base form_args
        result_form_args.update({
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
            result_form_args.update({
                'first_work_title': first_work_data['first_work_title'],
                'first_work_olid': first_work_data['first_work_olid'],
                'first_work_author_names': first_work_data['first_work_author_names'],
                'first_work_author_olids': first_work_data['first_work_author_olids']
            })

        # Now create the form with the result-specific form_args
        form = ConfirmBook(result_form_args)
        logger.info("=== Created Form ===")
        logger.info("Form data: %s", form.data)
        forms.append(form)

    # Add locations to context for the template
    context['locations'] = Location.objects.all()
    context['forms'] = forms
    
    # Add the first form as the default form for backward compatibility
    # This ensures templates that expect 'form' still work
    #if forms:
    #    context['form'] = forms[0]

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

def _author_name_matches(name, local_author, result):
    """Check if an author name matches a local author, including alternate names"""
    logger.info("=== Checking Author Name Match ===")
    logger.info("Comparing name: '%s' with local author: '%s'", name, local_author.primary_name)
    logger.info("Local author alternate names: %s", local_author.alternate_names)

    # Direct match check
    if name == local_author.primary_name:
        logger.info("Name matches local author exactly!")
        return True
    
    def normalize_name(n):
        # Remove quotes and content within them
        n = n.lower().replace(',', '')
        # If it's a pen name format (contains quotes), extract both base name and pen name
        if "'" in n:
            # Extract the base name (remove quoted section)
            base_name = n.split("'")[0].strip() + " " + n.split("'")[-1].strip()
            # Extract the pen name (get quoted section)
            pen_name = n.split("'")[1].strip()
            return [base_name, pen_name]
        return [n.strip()]

    # Get normalized variants of the local author's name
    name_variants = normalize_name(local_author.primary_name)
    logger.info("Looking for name variants: %s", name_variants)
    
    # Normalize the comparison name
    test_name = name.lower().replace(',', '').strip()
    logger.info("Normalized test name: %s", test_name)
    
    # Check if any variant matches
    for variant in name_variants:
        if variant == test_name:
            logger.info("Found matching name variant '%s'!", variant)
            return True
            
    # Check result's alternate names against local variants
    alt_names = []
    if isinstance(result, dict):
        if 'author_alternative_name' in result:
            alt_names.extend(result['author_alternative_name'])
        elif 'author_alternative_names' in result:  # Handle possible alternate key
            alt_names.extend(result['author_alternative_names'])
    
    logger.info("Result alternate names: %s", alt_names)
    alt_names = [alt.lower().replace(',', '').strip() for alt in alt_names]
    logger.info("Normalized alternate names: %s", alt_names)
    
    # Check if any variant appears in alternate names
    for variant in name_variants:
        if variant in alt_names:
            logger.info("Found matching name variant '%s' in alternate names!", variant)
            return True
            
    # Check if the OpenLibrary author has the same OLID
    if isinstance(result, dict):
        ol_author_id = None
        if isinstance(result.get('author_key'), list) and result['author_key']:
            ol_author_id = result['author_key'][0]
        
        logger.info("Comparing OLIDs - result: %s, local: %s", ol_author_id, local_author.olid)
        if ol_author_id and ol_author_id == local_author.olid:
            logger.info("OLID match found!")
            return True
            
    logger.info("No matches found")
    return False
