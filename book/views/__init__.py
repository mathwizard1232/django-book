from django.shortcuts import render

from .author_views import get_author, confirm_author
from .book_views import get_title, confirm_book
from .isbn_views import get_book_by_isbn
from .location_views import (
    manage_locations,
    get_rooms,
    get_bookcases,
    get_shelves,
    assign_location,
    update_shelf_notes,
    shelve_books,
    get_shelf_details
)
from .autocomplete_views import (
    author_autocomplete,
    title_autocomplete,
    test_autocomplete
)

def index(request):
    return render(request, 'index.html')

__all__ = [
    'index',
    'get_author',
    'confirm_author',
    'get_title',
    'confirm_book',
    'get_book_by_isbn',
    'manage_locations',
    'get_rooms',
    'get_bookcases',
    'get_shelves',
    'assign_location',
    'update_shelf_notes',
    'shelve_books',
    'get_shelf_details',
    'author_autocomplete',
    'title_autocomplete',
    'test_autocomplete',
]
