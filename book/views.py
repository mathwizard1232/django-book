import logging
import urllib.parse

from django import forms
from django.http import HttpResponseRedirect
from django.http.response import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .utils.ol_client import CachedOpenLibrary

from .forms import AuthorForm, ConfirmAuthorForm, ConfirmAuthorFormWithBio, TitleForm, TitleGivenAuthorForm, ConfirmBook, LocationForm, LocationEntityForm
from .models import Author, Book, Location, Room, Bookcase, Shelf, Work, Edition, Copy

logger = logging.getLogger(__name__)

DIVIDER = " ::: "

def index(request):
    return render(request, 'index.html')

def get_author(request):
    """ Render a form requesting author name, then redirect to confirmation of details """
    if request.method == 'POST':
        form = AuthorForm(request.POST)
        if form.is_valid():
            # Send to a page which will attempt to look up this author name and confirm the selection
            name = form.cleaned_data['author_name']
            return HttpResponseRedirect(f'/confirm-author.html?author_name={name}')
    form = AuthorForm()
    return render(request, 'author.html', {'form': form})

def confirm_author(request):
    """ Do a lookup of this author by the name sent and display and confirm details from OpenLibrary """
    if request.method == 'GET':
        name = request.GET['author_name']
        if DIVIDER in name:
            # This is an autocomplete result already known locally
            # Directly send them to title entry
            name, olid = name.split(DIVIDER)
            return HttpResponseRedirect(f'/title.html?author_olid={olid}&author_name={name}')
        ol = CachedOpenLibrary()
        results = ol.Author.search(name, 2)
        if not results:
            return HttpResponseRedirect('/author')  # If we get a bad request, just have them try again
        first_author = results[0]
        first_olid = first_author['key'][9:]  # remove "/authors/" prefix
        first_author_full = ol.Author.get(first_olid)
        logger.info("First author full details: %s", vars(first_author_full))
        bio = first_author_full.bio
        
        logger.info("Author bio for %s: %s", first_author['name'], bio if bio else "No biography available")
        
        form = ConfirmAuthorForm({'author_olid' :first_olid, 'author_name': first_author['name'], 'search_name': name})

        if bio:
            form = ConfirmAuthorFormWithBio({'author_olid' :first_olid, 'author_name': first_author['name'], 'search_name': name, 'bio': bio})
        form2 = None
        if len(results) > 1:
            # NOTE: adding this because sometimes even with full name first result is wrong
            second_author = results[1]
            second_olid = second_author['key'][9:]
            second_author_full = ol.Author.get(second_olid)
            logger.info("Second author full details: %s", vars(second_author_full))
            second_bio = second_author_full.bio
            form2 = ConfirmAuthorForm({'author_olid': second_olid, 'author_name': second_author['name'], 'search_name': name})
            if second_bio:
                form2 = ConfirmAuthorFormWithBio({'author_olid': second_olid, 'author_name': second_author['name'], 'search_name': name, 'bio': second_bio})
        return render(request, 'confirm-author.html', {'form': form, 'form2': form2})
    if request.method == 'POST':
        # This is a confirmed author. Ensure that they have been recorded.
        name = request.POST['author_name']
        olid = request.POST['author_olid']
        search_name = request.POST['search_name']

        author_lookup_qs = Author.objects.filter(olid=olid)
        if not author_lookup_qs:
            author = Author.objects.create(
                olid = olid,
                primary_name = name,
                search_name = search_name,
            )
            logger.info("Recorded new author: %s (%s) AKA %s)", name, olid, search_name)

        # Finally, redirect them off to the title lookup
        return HttpResponseRedirect(f'/title.html?author_olid={olid}&author_name={name}')

def get_title(request):
    """ Do a lookup of a book by title, with a particular author potentially already set """
    if request.method == 'GET':
        if 'author_olid' in request.GET:
            a_olid = request.GET['author_olid']
            form = TitleGivenAuthorForm({'author_olid': a_olid, 'author_name': request.GET['author_name']})
            # Attempting to override with runtime value for url as a kludge for how to pass the author OLID
            data_url = "/author/" + a_olid +  "/title-autocomplete"
            logger.info("new data url %s", data_url)
            form.fields['title'].widget=forms.TextInput(attrs={'autofocus': 'autofocus',
                'class': 'basicAutoComplete',
                'data-url': data_url,
                'autocomplete': 'off'})
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
    ol = CachedOpenLibrary()
    # Build the link back to the author page
    params = {}
    params = request.GET if request.method == 'GET' else params
    params = request.POST if request.method == 'POST' else params
    if 'title' not in params:
        return HttpResponse('Title required')
    search_title = params['title']
    author = None  # search just on title if no author chosen
    args = {}
    author_olid = None
    if 'author_name' in params:  # use author name as default if given; save in context
        author=params['author_name']
        args['author_name'] = author
    if 'author_olid' in params:  # prefer OpenLibrary ID if specified
        author_olid=params['author_olid']
        args['author_olid'] = author_olid
        author = author_olid
    context = {'title_url': "title.html?" + urllib.parse.urlencode(args)}

    if DIVIDER in search_title:
        # This is an autocomplete result already known locally
        # No need to confirm; go ahead to next step
        title, olid = search_title.split(DIVIDER)
        args['title'] = title
        args['work_olid'] = olid
        context['form'] = ConfirmBook(args)
        #return render(request, 'just-entered-book.html', context)
        # temporary hack for faster entry loop; eventually add a mode to switch where we go
        # TODO: real switching
        return HttpResponseRedirect('/author')

    # This is the OpenLibrary lookup using author if given (by ID, hopefully) and title
    # It gives the single closest match in its view
    # With some hacking of the client, multiple results could be returned for alternate selections if needed
    logger.info("Searching OpenLibrary with author='%s', title='%s', limit=2", author, search_title)
    try:
        results = ol.Work.search(author=author, title=search_title, limit=2)
        logger.info("OpenLibrary search results type: %s", type(results))
        if hasattr(results, '__iter__') and not isinstance(results, (str, bytes)):
            logger.info("Got list of %d results", len(results))
            for i, result in enumerate(results):
                logger.info("Result %d: %s", i+1, vars(result))
        else:
            logger.info("Got single result: %s", vars(results) if results else None)
    except Exception as e:
        logger.exception("Error during OpenLibrary search")
        raise

    if not results:
        # try searching by author name if we have an author_olid
        if author_olid:
            try:
                ol_author = ol.Author.get(author_olid)
                logger.info("Trying search with author name '%s' instead of ID", ol_author.name)
                results = ol.Work.search(author=ol_author.name, title=search_title, limit=2)
                if results:
                    logger.info("Found works by author name '%s' after ID search failed", ol_author.name)
                logger.info("Results from name search: %s", results)
            except Exception as e:
                logger.warning("Failed to lookup author by ID %s: %s", author_olid, e)

        # If still no result or no author_olid, try title-only search
        if not results:
            logger.info("Trying title-only search for '%s'", search_title)
            results = ol.Work.search(title=search_title, limit=2)
            logger.info("Results from title-only search: %s", results)
            if not results:
                # TODO: better handling
                raise Exception("no result")
        
    display_title = results[0].title
    work_olid = results[0].identifiers['olid'][0]
    publish_year = results[0].publish_date
    publisher = results[0].publisher

    # TODO: This selects the first author, but should display multiple authors, or at least prefer the specified author
    author_name = results[0].authors[0]['name']

    # This block is setting up the context and form to display the book
    args['title'] = display_title
    args['work_olid'] = work_olid
    args['publisher'] = publisher
    args['publish_year'] = publish_year
    context['form'] = ConfirmBook(args)
    context['author_name'] = author_name

    # Display confirmation form, or
    if request.method == 'GET':
        # Add locations to context for the template
        context['locations'] = Location.objects.all()
        return render(request, 'confirm-book.html', context)
    # Process confirmation and direct to next step
    elif request.method == 'POST':
        action = request.POST.get('action', 'Confirm Without Shelving')
        
        # If we don't have a record of this Work yet, record it now.
        work_qs = Work.objects.filter(olid=work_olid)
        if not work_qs:
            work = Work.objects.create(
                olid=work_olid,
                title=display_title,
                search_name=search_title,
                type='NOVEL',  # Default type, could be made configurable
            )
            work.authors.add(Author.objects.get(olid=author_olid))
            logger.info("Added new Work %s (%s) AKA %s", display_title, work_olid, search_title)
        else:
            work = work_qs[0]

        # Create a default Edition
        edition = Edition.objects.create(
            work=work,
            publisher=publisher if publisher else "Unknown",
            format="PAPERBACK",   # Default format
        )

        # Create a Copy with optional shelf assignment
        copy_data = {
            'edition': edition,
            'condition': "GOOD",  # Default condition
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
        context['copy'] = copy

        #return render(request, 'just-entered-book.html', context)
        return HttpResponseRedirect('/author/')

def author_autocomplete(request):
    """ Return a list of autocomplete suggestions for authors """
    # TODO: First attempt to select from authors already in library locally
    # TODO: Add ability to suggest authors with zero characters
    # TODO: Sort authors by number of books by them in the local library
    # Initial version: return the suggestions from OpenLibrary
    if not 'q' in request.GET:
        return JsonResponse()
    search_str = request.GET['q']
    # first, look for local results
    author_qs = Author.objects.filter(search_name__contains=search_str)
    if author_qs:
        author = author_qs[0]
        logger.info("Successful local lookup of author candidate of %s (%s) on %s", author.primary_name, author.olid, search_str )
        # We're using the DIVIDER as a kludge to pass these two values together in a single value
        return JsonResponse([author.primary_name + DIVIDER + author.olid for author in author_qs], safe=False)  # safe=False required to allow list rather than dict

    # otherwise, do an OpenLibrary API search
    RESULTS_LIMIT = 5
    ol = CachedOpenLibrary()
    authors = ol.Author.search(search_str, RESULTS_LIMIT)
    names = [author['name'] for author in authors]  # TODO: this should really be going by OLID rather than by name;
    return JsonResponse(names, safe=False)  # safe=False required to allow list rather than dict

def title_autocomplete(request, oid):
    """
    Returns an autocomplete suggestion for the work
    Narrows down by author specified by oid
    """
    if 'q' not in request.GET:
        return HttpResponseBadRequest("q must be specified")

    # first attempt local lookup
    title=request.GET['q']
    author = Author.objects.get(olid = oid)
    book_qs = Book.objects.filter(author=author, search_name__contains=title)
    if book_qs:
        book = book_qs[0]
        logger.info("Successful local lookup of book candidate %s (%s) on %s", book.title, book.olid, title)
        # We're using the DIVIDER as a kludge to pass these two values together in a single value
        return JsonResponse([book.title + DIVIDER + book.olid for book in book_qs], safe=False)

    # then try to do OpenLibrary API lookup
    ol = CachedOpenLibrary()    
    result = ol.Work.search(author=oid, title=title)
    if not result:
        logger.warning("Failed to lookup title autocomplete for author oid %s and title %s", oid, title)
        return JsonResponse({})
    names = [result.title]
    return JsonResponse(names, safe=False)  # safe=False required to allow list rather than dict

def test_autocomplete(request):
    """ Test page from the bootstrap autocomplete repo to figure out how to get dropdowns working right """
    return render(request, 'test-autocomplete.html')

def list(request):
    """ Display summary of what's in library """
    # Get authors who have at least one work
    authors_with_works = Author.objects.filter(work__isnull=False).distinct()
    works = Work.objects.all().prefetch_related('authors')
    context = {'authors': authors_with_works, 'works': works}
    return render(request, 'list.html', context)

def manage_locations(request):
    if request.method == 'POST':
        form = LocationEntityForm(request.POST)
        if form.is_valid():
            entity_type = form.cleaned_data['entity_type']
            name = form.cleaned_data['name']
            notes = form.cleaned_data.get('notes', '')

            if entity_type == 'LOCATION':
                Location.objects.create(
                    name=name,
                    type=form.cleaned_data['type'],
                    address=form.cleaned_data.get('address', ''),
                    notes=notes
                )
            elif entity_type == 'ROOM':
                Room.objects.create(
                    name=name,
                    type=form.cleaned_data['room_type'],
                    floor=form.cleaned_data.get('floor', 1),
                    location=form.cleaned_data['parent_location'],
                    notes=notes
                )
            elif entity_type == 'BOOKCASE':
                Bookcase.objects.create(
                    name=name,
                    shelf_count=form.cleaned_data['shelf_count'],
                    room=form.cleaned_data.get('parent_room'),
                    location=form.cleaned_data.get('parent_location'),
                    notes=notes
                )
            return HttpResponseRedirect('/locations/')
    else:
        form = LocationEntityForm()
    
    # Get all location entities for display
    locations = Location.objects.all()
    rooms = Room.objects.select_related('location').all()
    bookcases = Bookcase.objects.select_related('room', 'location').all()
    
    context = {
        'locations': locations,
        'rooms': rooms,
        'bookcases': bookcases,
        'shelves': Shelf.objects.all().order_by('bookcase', 'position'),  # Make sure shelves are ordered
        'form': form,
    }
    return render(request, 'locations.html', context)

def get_rooms(request, location_id):
    rooms = Room.objects.filter(location_id=location_id)
    return JsonResponse([{'id': r.id, 'name': r.name} for r in rooms], safe=False)

def get_bookcases(request, room_id):
    bookcases = Bookcase.objects.filter(room_id=room_id)
    return JsonResponse([{'id': b.id, 'name': b.name} for b in bookcases], safe=False)

def get_shelves(request, bookcase_id):
    shelves = Shelf.objects.filter(bookcase_id=bookcase_id)
    return JsonResponse([{
        'id': s.id, 
        'name': f'Shelf {s.position}',
        'notes': s.notes
    } for s in shelves], safe=False)

def assign_location(request, copy_id):
    if request.method == 'POST':
        copy = Copy.objects.get(id=copy_id)
        
        # Clear existing location data
        copy.location = None
        copy.room = None
        copy.bookcase = None
        copy.shelf = None
        
        # Assign new location data
        if request.POST.get('location'):
            copy.location_id = request.POST['location']
        if request.POST.get('room'):
            copy.room_id = request.POST['room']
        if request.POST.get('bookcase'):
            copy.bookcase_id = request.POST['bookcase']
        if request.POST.get('shelf'):
            copy.shelf_id = request.POST['shelf']
        
        copy.save()
        
        # Redirect to success page or back to the form
        return HttpResponseRedirect(reverse('index'))
    
    return HttpResponseBadRequest("POST request required")

@require_http_methods(["POST"])
def update_shelf_notes(request, shelf_id):
    try:
        shelf = Shelf.objects.get(id=shelf_id)
        shelf.notes = request.POST.get('notes', '')
        shelf.save()
        return JsonResponse({'status': 'success'})
    except Shelf.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Shelf not found'}, status=404)

def shelve_books(request):
    """Display and manage books that need to be shelved"""
    if request.method == 'POST':
        shelf_id = request.POST.get('shelf_id')
        copy_ids = request.POST.getlist('copy_ids')
        
        if shelf_id and copy_ids:
            shelf = Shelf.objects.get(id=shelf_id)
            # Update all selected copies
            Copy.objects.filter(id__in=copy_ids).update(
                shelf_id=shelf_id,
                location=shelf.bookcase.get_location(),
                room=shelf.bookcase.room,
                bookcase=shelf.bookcase
            )
            return HttpResponseRedirect(reverse('shelve_books'))
    
    # Get all copies that don't have a shelf assigned
    unshelved_copies = Copy.objects.filter(
        shelf__isnull=True
    ).select_related(
        'edition__work',
        'location',
        'room',
        'bookcase'
    )
    
    # Get all locations for the location hierarchy
    locations = Location.objects.all()
    
    context = {
        'unshelved_copies': unshelved_copies,
        'locations': locations,
    }
    
    return render(request, 'shelve-books.html', context)

def get_shelf_details(request, shelf_id):
    """Return shelf details including notes"""
    try:
        shelf = Shelf.objects.get(id=shelf_id)
        return JsonResponse({
            'id': shelf.id,
            'position': shelf.position,
            'notes': shelf.notes
        })
    except Shelf.DoesNotExist:
        return JsonResponse({'error': 'Shelf not found'}, status=404)
