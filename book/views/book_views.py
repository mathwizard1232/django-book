import logging
import urllib.parse
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render
from ..forms import TitleForm, TitleGivenAuthorForm, ConfirmBook, TitleOnlyForm
from ..models import Author, Work, Edition, Copy, Location, Shelf
from ..utils.ol_client import CachedOpenLibrary
from .autocomplete_views import DIVIDER
import json

logger = logging.getLogger(__name__)

def get_title(request):
    """ Do a lookup of a book by title, with a particular author potentially already set """
    if request.method == 'GET':
        if 'author_olid' in request.GET:
            a_olid = request.GET['author_olid']
            form = TitleGivenAuthorForm({
                'author_olid': a_olid, 
                'author_name': request.GET['author_name'],
                'author_role': request.GET.get('author_role', 'AUTHOR')
            })
            # Attempting to override with runtime value for url as a kludge for how to pass the author OLID
            data_url = "/author/" + a_olid + "/title-autocomplete"
            logger.info("new data url %s", data_url)
            form.fields['title'].widget.attrs.update({
                'autofocus': 'autofocus',
                'class': 'basicAutoComplete',
                'data-url': data_url,
                'autocomplete': 'off'
            })
        else:
            form = TitleForm()
        return render(request, 'title.html', {'form': form})
    
    if request.method == 'POST':
        post_url = f"/confirm-book.html?title={request.POST['title']}"
        if 'author_olid' in request.POST:
            post_url += f"&author_olid={request.POST['author_olid']}"
        if 'author_name' in request.POST:
            post_url += f"&author_name={request.POST['author_name']}"
        return HttpResponseRedirect(post_url)

def confirm_book(request):
    """ Given enough information for a lookup, retrieve the most likely book and confirm it's correct """
    if request.method == 'POST':
        return _handle_book_confirmation(request)
    else:
        return _handle_book_search(request)

def _handle_book_confirmation(request):
    """Process the confirmed book selection and create local records"""
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
    
    # Get the work_olid from the POST data
    work_olid = request.POST.get('work_olid')
    if not work_olid:
        return HttpResponseBadRequest('work_olid required')

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
    
    # Get author roles
    author_roles = {}
    if request.POST.get('author_roles'):
        try:
            author_roles = json.loads(request.POST.get('author_roles'))
            logger.info("Parsed author_roles: %s", author_roles)
        except json.JSONDecodeError:
            logger.warning("Failed to parse author_roles JSON")
            logger.warning("Raw author_roles value: %r", request.POST.get('author_roles'))
    else:
        logger.warning("No author_roles found in POST data")
        logger.info("POST data: %s", dict(request.POST))

    # Get author information with detailed logging
    author_olids = request.POST.get('author_olids', '')
    author_names = request.POST.get('author_names', '')
    logger.info("Author OLIDs: %s", author_olids)
    logger.info("Author Names: %s", author_names)
    logger.info("Author Roles mapping: %s", author_roles)

    # Backwards compatibility - if author_olids is empty but author_olid exists, use that
    if not author_olids and request.POST.get('author_olid'):
        author_olids = request.POST.get('author_olid')
        logger.info("Using singular author_olid for backwards compatibility: %s", author_olids)
    
    # Split into list, filtering out empty strings
    author_olids = [olid for olid in author_olids.split(',') if olid]
    logger.info("Final author_olids list: %s", author_olids)

    # Track if this is a new work for the message
    is_new_work = False
    
    # Handle work creation
    work_qs = Work.objects.filter(olid=work_olid)
    if not work_qs:
        is_new_work = True
        work = Work.objects.create(
            olid=work_olid,
            title=clean_title,
            search_name=search_name,
            type='NOVEL',
        )
        
        # Add authors and editors based on roles
        for olid, name in zip(author_olids, author_names.split(',')):
            author = Author.objects.get_or_fetch(olid)
            if author:
                # Ensure author is saved to database
                if not author.pk:  # If author doesn't have a primary key, it needs to be saved
                    author.save()
                    
                role = author_roles.get(name.strip(), 'AUTHOR')
                if role == 'EDITOR':
                    logger.info("Found author object for editor: %s (ID: %s)", author.primary_name, author.pk)
                    work.editors.add(author)
                    # Verify addition
                    logger.info("After adding editor - work.editors count: %d", work.editors.count())
                else:
                    logger.info("Found author object for author: %s (ID: %s)", author.primary_name, author.pk)
                    work.authors.add(author)
                    # Verify addition
                    logger.info("After adding author - work.authors count: %d", work.authors.count())
            else:
                logger.warning("No author found for OLID: %s, name: %s", olid, name)
        
        # Verify the additions
        work.refresh_from_db()
        logger.info("Work authors: %s", [a.primary_name for a in work.authors.all()])
        logger.info("Work editors: %s", [e.primary_name for e in work.editors.all()])

        logger.info("Added new Work %s (%s) AKA %s with %d authors/editors", 
                   clean_title, work_olid, search_name, len(author_olids))
    else:
        work = work_qs[0]

    # Handle multivolume specifics if needed
    if is_multivolume:
        # Get authors and editors before creating volumes
        authors = []
        editors = []
        for olid, name in zip(author_olids, author_names.split(',')):
            if olid:
                author = Author.objects.get_or_fetch(olid)
                if author:
                    role = author_roles.get(name.strip(), 'AUTHOR')
                    if role == 'EDITOR':
                        editors.append(author)
                    else:
                        authors.append(author)

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

    return HttpResponseRedirect(f'/author/?message={message}')

def _handle_book_search(request):
    """Search for and display potential book matches"""
    ol = CachedOpenLibrary()
    
    # Get search parameters
    params = request.GET
    if 'title' not in params:
        return HttpResponseBadRequest('Title required')
    
    search_title = params['title']
    args = {}
    
    # Build author context
    if 'author_name' in params:
        args['author_name'] = params['author_name']
    if 'author_olid' in params:
        args['author_olid'] = params['author_olid']
    
    context = {'title_url': "title.html?" + urllib.parse.urlencode(args)}

    # Check if we're in collection mode
    if 'collection_first_work' in request.session:
        context['first_work'] = request.session['collection_first_work']
        template = 'confirm-collection.html'
    else:
        template = 'confirm-book.html'

    # Handle local autocomplete results
    if DIVIDER in search_title:
        title, olid = search_title.split(DIVIDER)
        args['title'] = title
        args['work_olid'] = olid
        
        # Check for existing work with copies
        existing_work = Work.objects.filter(olid=olid).first()
        if existing_work and existing_work.edition_set.filter(copy__isnull=False).exists():
            context = {
                'work': existing_work,
                'form_data': args,
                'locations': Location.objects.all()
            }
            return render(request, 'confirm-duplicate.html', context)
            
        context['form'] = ConfirmBook(args)
        return HttpResponseRedirect('/author')

    # Search OpenLibrary and build forms
    results = _search_openlibrary(ol, search_title, args.get('author_olid'), args.get('author_name'))
    
    # Build forms for results
    forms = []
    for result in results:
        display_title = result.title
        work_olid = result.identifiers['olid'][0]
        
        # Check for existing work with copies before creating form
        logger.info("Checking for existing work with copies for %s", work_olid)
        existing_work = Work.objects.filter(olid=work_olid).first()
        if existing_work and existing_work.edition_set.filter(copy__isnull=False).exists():
            logger.info("Found existing work with copies for %s", work_olid)
            context = {
                'work': existing_work,
                'form_data': {
                    'title': display_title,
                    'work_olid': work_olid,
                    'author_names': result.authors[0]['name'],
                    'author_olids': result.authors[0].get('olid', '')
                },
                'locations': Location.objects.all()
            }
            return render(request, 'confirm-duplicate.html', context)
            
        publish_year = result.publish_date
        publisher = result.publisher
        author_name = result.authors[0]['name']

        # Get author OLID either from args or from search result
        author_olids = args.get('author_olid', '')
        if not author_olids and 'key' in result.authors[0]:
            author_olids = result.authors[0]['key'].replace('/authors/', '')

        form_args = {
            'title': display_title,
            'work_olid': work_olid,
            'author_olids': author_olids,
            'author_names': author_name
        }
        logger.info("Final form_args: %s", form_args)
        
        logger.info("Form args before creating ConfirmBook form: %s", form_args)
        logger.info("Author names from form_args: %s", form_args.get('author_names'))
        logger.info("Author OLIDs from form_args: %s", form_args.get('author_olids'))
        
        forms.append(ConfirmBook(form_args))
        
        # If this is the first result and we're in collection mode, add it as second_work
        if 'collection_first_work' in request.session and len(forms) == 1:
            context['second_work'] = {
                'title': result.title,
                'work_olid': result.identifiers['olid'][0],
                'author_names': result.authors[0]['name'] if result.authors else '',
                'author_olids': form_args['author_olids'],
                'publisher': result.publisher[0] if hasattr(result, 'publisher') and result.publisher else 'Unknown'
            }

    # Add locations to context for the template
    context['locations'] = Location.objects.all()
    context['forms'] = forms
    
    return render(request, template, context)

def _search_openlibrary(ol, title, author_olid=None, author_name=None):
    """Search OpenLibrary for works matching title and author"""
    results = []
    
    # Try initial search with author ID if available
    if author_olid:
        logger.info("Searching OpenLibrary with author='%s', title='%s', limit=2", author_olid, title)
        try:
            results = ol.Work.search(author=author_olid, title=title, limit=2)
        except Exception as e:
            logger.exception("Error during OpenLibrary search")
            raise

    # If no results with ID, try author name
    if not results and author_name:
        try:
            logger.info("Trying search with author name '%s'", author_name)
            name_results = ol.Work.search(author=author_name, title=title, limit=2)
            if name_results:
                results.extend(name_results)
            
            # If still no results, try with simplified author name (remove middle initial)
            if not results and ' ' in author_name:
                # Split name and check if we have what looks like a middle initial
                name_parts = author_name.split()
                if len(name_parts) > 2 and len(name_parts[1]) <= 2:
                    simplified_name = f"{name_parts[0]} {name_parts[-1]}"
                    logger.info("Trying search with simplified author name '%s'", simplified_name)
                    simple_results = ol.Work.search(author=simplified_name, title=title, limit=2)
                    if simple_results:
                        results.extend(simple_results)
                        
            # If still no results, try with last name only
            if not results and ' ' in author_name:
                # Get the last word as the last name
                last_name = author_name.split()[-1]
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
    """Convert a single Work confirmation into a Collection creation flow"""
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
        
    # Store the first work's details in session
    request.session['collection_first_work'] = {
        'title': request.POST.get('title'),
        'work_olid': request.POST.get('work_olid'),
        'author_names': request.POST.get('author_names'),
        'author_olids': request.POST.get('author_olids'),
        'publisher': request.POST.get('publisher'),
    }
    
    # Redirect to author selection for second work
    return HttpResponseRedirect('/author/')

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
