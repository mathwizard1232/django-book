import logging
import urllib.parse
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render
from ..forms import TitleForm, TitleGivenAuthorForm, ConfirmBook
from ..models import Author, Work, Edition, Copy, Location, Shelf
from ..utils.ol_client import CachedOpenLibrary
from .autocomplete_views import DIVIDER

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
        
    # Get other required fields from POST
    display_title = request.POST.get('title')
    # Strip any volume number from the title
    clean_title = Work.strip_volume_number(display_title)
    author_olid = request.POST.get('author_olid')
    publisher = request.POST.get('publisher')
    search_title = request.POST.get('title', display_title)
    
    # Handle multi-volume works
    is_multivolume = request.POST.get('is_multivolume') == 'on'
    entry_type = request.POST.get('entry_type')
    volume_number = request.POST.get('volume_number')
    volume_count = request.POST.get('volume_count')
    
    # Get the author role
    author_role = request.POST.get('author_role', 'AUTHOR')
    
    # Get the author information
    author_olids = request.POST.get('author_olids', '')
    
    # Backwards compatibility - if author_olids is empty but author_olid exists, use that
    if not author_olids and request.POST.get('author_olid'):
        author_olids = request.POST.get('author_olid')
        logger.info("Using singular author_olid for backwards compatibility: %s", author_olids)
    
    # Split into list, filtering out empty strings
    author_olids = [olid for olid in author_olids.split(',') if olid]
    
    # Track if this is a new work for the message
    is_new_work = False
    
    # Handle work creation
    work_qs = Work.objects.filter(olid=work_olid)
    if not work_qs:
        is_new_work = True
        work = Work.objects.create(
            olid=work_olid,
            title=clean_title,
            search_name=search_title,
            type='NOVEL',
        )
        
        # Add all authors
        for author_olid in author_olids:
            if not author_olid:
                logger.warning("Empty author_olid in sequence - skipping")
                continue
                
            if author_role == 'AUTHOR':
                work.authors.add(Author.objects.get_or_fetch(author_olid))
            else:
                work.editors.add(Author.objects.get_or_fetch(author_olid))
            logger.info("Added author %s to work %s", author_olid, work_olid)
        
        logger.info("Added new Work %s (%s) AKA %s with %d authors", 
                   clean_title, work_olid, search_title, len(author_olids))
    else:
        work = work_qs[0]

    # Handle multivolume specifics if needed
    if is_multivolume:
        # Get authors before creating volumes
        authors = []
        for author_olid in author_olids:
            if author_olid:
                authors.append(Author.objects.get_or_fetch(author_olid))

        if entry_type == 'COMPLETE':
            work, volumes = Work.create_volume_set(
                title=clean_title,
                volume_count=int(volume_count),
                authors=authors if author_role == 'AUTHOR' else None,
                editors=authors if author_role == 'EDITOR' else None,
                olid=work_olid,
                search_name=search_title,
                type='NOVEL'
            )
        elif entry_type == 'SINGLE':
            work, volume = Work.create_single_volume(
                set_title=clean_title,
                volume_number=int(volume_number) if volume_number else 1,
                authors=authors if author_role == 'AUTHOR' else None,
                editors=authors if author_role == 'EDITOR' else None,
                olid=work_olid,
                search_name=search_title,
                type='NOVEL'
            )
            volumes = [volume]
        elif entry_type == 'PARTIAL':
            volume_numbers = [int(v) for v in request.POST.get('volume_numbers', '').split(',') if v]
            work, volumes = Work.create_partial_volume_set(
                title=clean_title,
                volume_numbers=volume_numbers,
                authors=authors if author_role == 'AUTHOR' else None,
                editors=authors if author_role == 'EDITOR' else None,
                olid=work_olid,
                search_name=search_title,
                type='NOVEL'
            )

    # Create Editions and Copies for all volumes if multivolume
    if is_multivolume:
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

    # Add message to redirect
    message = 'new_work' if is_new_work else 'new_copy'
    return HttpResponseRedirect(f'/author/?message={message}&title={urllib.parse.quote(display_title)}')

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

    # Search OpenLibrary
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

    # Add locations to context for the template
    context['locations'] = Location.objects.all()
    context['forms'] = forms
    
    return render(request, 'confirm-book.html', context)

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
