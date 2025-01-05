import logging
import urllib.parse

from django import forms
from django.http import HttpResponseRedirect
from django.http.response import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .utils.ol_client import CachedOpenLibrary

from .forms import AuthorForm, ConfirmAuthorForm, ConfirmAuthorFormWithBio, TitleForm, TitleGivenAuthorForm, ConfirmBook, LocationForm, LocationEntityForm, ISBNForm
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
    
    action = request.POST.get('action', 'Confirm Without Shelving')
    
    # Get the work_olid from the POST data
    work_olid = request.POST.get('work_olid')
    if not work_olid:
        return HttpResponseBadRequest('work_olid required')
        
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
    
    # Get or create the work(s)
    if is_multivolume:
        author = Author.objects.get(olid=author_olid)
        if entry_type == 'SINGLE':
            parent_work, volume_work = Work.create_single_volume(
                set_title=clean_title,
                volume_number=int(volume_number),
                authors=author,
                olid=work_olid,
                search_name=search_title,
                type='COLLECTION'
            )
            # Only create edition/copy for the volume work
            work = volume_work
            
            # Don't create edition/copy for parent_work
            
        elif entry_type == 'COMPLETE':
            if not volume_count:
                return HttpResponseBadRequest('volume_count required for COMPLETE set')
            parent_work, volume_works = Work.create_volume_set(
                title=clean_title,
                authors=author,
                volume_count=int(volume_count),
                olid=work_olid,
                search_name=search_title,
                type='COLLECTION'
            )
            # Create editions and copies for all volumes
            for volume_work in volume_works:
                edition = Edition.objects.create(
                    work=volume_work,
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
            return HttpResponseRedirect('/author/')
        elif entry_type == 'PARTIAL':
            if not volume_count or not volume_number:
                return HttpResponseBadRequest('volume_count and volume_number required for PARTIAL set')
            parent_work, volume_works = Work.create_partial_volume_set(
                title=clean_title,
                authors=author,
                volume_numbers=[int(volume_number)],
                olid=work_olid,
                search_name=search_title,
                type='COLLECTION'
            )
            work = volume_works[0]  # Use the first (only) volume for edition/copy creation
        else:
            return HttpResponseBadRequest('Invalid entry_type')
    else:
        # Handle non-multivolume work as before
        work_qs = Work.objects.filter(olid=work_olid)
        if not work_qs:
            work = Work.objects.create(
                olid=work_olid,
                title=clean_title,
                search_name=search_title,
                type='NOVEL',
            )
            work.authors.add(Author.objects.get(olid=author_olid))
            logger.info("Added new Work %s (%s) AKA %s", clean_title, work_olid, search_title)
        else:
            work = work_qs[0]

    # Create a default Edition
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

    return HttpResponseRedirect('/author/')

def _handle_book_search(request):
    """Search for and display potential book matches"""
    ol = CachedOpenLibrary()
    
    # Get search parameters
    params = request.GET
    if 'title' not in params:
        return HttpResponse('Title required')
    
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
        context['form'] = ConfirmBook(args)
        return HttpResponseRedirect('/author')

    # Search OpenLibrary
    results = _search_openlibrary(ol, search_title, args.get('author_olid'), args.get('author_name'))
    
    # Build forms for results
    forms = []
    for result in results:
        display_title = result.title
        work_olid = result.identifiers['olid'][0]
        publish_year = result.publish_date
        publisher = result.publisher
        author_name = result.authors[0]['name']

        form_args = {
            'title': display_title,
            'work_olid': work_olid,
            'publisher': publisher,
            'publish_year': publish_year,
            'author_name': author_name
        }
        if args.get('author_olid'):
            form_args['author_olid'] = args['author_olid']
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
    """Display summary of what's in library"""
    # Get authors who have at least one work, sorted by last name
    authors_with_works = Author.objects.filter(work__isnull=False).distinct()
    authors_with_works = sorted(
        authors_with_works,
        key=lambda x: x.primary_name.split()[-1].lower()
    )
    
    # Get works and organize by location hierarchy
    works = Work.objects.filter(
        is_multivolume=False  # Only include individual volumes, not parent sets
    ).prefetch_related(
        'authors',
        'edition_set__copy_set__location',
        'edition_set__copy_set__room',
        'edition_set__copy_set__bookcase',
        'edition_set__copy_set__shelf'
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
        'unassigned_works': unassigned_works
    }
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

def get_book_by_isbn(request):
    """Handle ISBN lookup form submission"""
    if request.method == 'POST':
        form = ISBNForm(request.POST)
        if form.is_valid():
            isbn = form.cleaned_data['isbn']
            try:
                ol = CachedOpenLibrary()
                book = ol.Work.search_by_isbn(isbn)
                
                if book:
                    # Prepare form data for confirmation
                    form_data = {
                        'title': book.title,
                        'work_olid': book.identifiers['olid'][0],
                        'publisher': book.publisher,
                        'publish_year': book.publish_date
                    }
                    
                    # Add author info if available
                    if book.authors:
                        author = book.authors[0]  # author is now a dict
                        form_data['author_name'] = author['name']
                        if 'olid' in author:
                            form_data['author_olid'] = author['olid']
                    
                    confirm_form = ConfirmBook(form_data)
                    return render(request, 'confirm-book.html', {
                        'forms': [confirm_form],
                        'locations': Location.objects.all()
                    })
                else:
                    form.add_error('isbn', 'No book found with this ISBN')
            except Exception as e:
                logger.exception("Error searching by ISBN")
                form.add_error('isbn', f'Error looking up ISBN: {str(e)}')
    else:
        form = ISBNForm()
    
    return render(request, 'isbn.html', {'form': form})
