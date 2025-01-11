import logging
from django.http import HttpResponseRedirect, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from ..forms import LocationForm, LocationEntityForm
from ..models import Location, Room, Bookcase, Shelf, Copy

logger = logging.getLogger(__name__)

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

@require_http_methods(["GET", "POST"])
def reshelve_books(request):
    if request.method == "POST":
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
            return HttpResponseRedirect(reverse('reshelve_books'))
    
    # Get all locations for the location hierarchy
    locations = Location.objects.all()
    
    context = {
        'locations': locations,
    }
    
    return render(request, 'reshelve-books.html', context)

@require_http_methods(["GET"])
def get_books_by_location(request, location_id):
    """API endpoint to get books for a location"""
    copies = Copy.objects.filter(
        location_id=location_id
    ).select_related(
        'edition__work',
        'location',
        'room',
        'bookcase',
        'shelf'
    )
    
    books = [{
        'copy_id': copy.id,
        'title': copy.edition.work.title,
        'authors': ', '.join(author.primary_name for author in copy.edition.work.authors.all()),
        'location_path': f"{copy.location.name} > {copy.room.name if copy.room else ''} > "
                        f"{copy.bookcase.name if copy.bookcase else ''} > "
                        f"Shelf {copy.shelf.position if copy.shelf else ''}"
    } for copy in copies]
    
    return JsonResponse(books, safe=False)

@require_http_methods(["GET"])
def get_shelf_books(request, shelf_id):
    """API endpoint to get books for a shelf"""
    copies = Copy.objects.filter(
        shelf_id=shelf_id
    ).select_related(
        'edition__work',
        'location',
        'room',
        'bookcase',
        'shelf'
    )
    
    books = [{
        'copy_id': copy.id,
        'title': copy.edition.work.title,
        'authors': ', '.join(author.primary_name for author in copy.edition.work.authors.all()),
        'location_path': f"{copy.location.name} > {copy.room.name if copy.room else ''} > "
                        f"{copy.bookcase.name if copy.bookcase else ''} > "
                        f"Shelf {copy.shelf.position if copy.shelf else ''}"
    } for copy in copies]
    
    return JsonResponse(books, safe=False)
