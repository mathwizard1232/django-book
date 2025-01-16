from django.shortcuts import render

from .author_views import get_author, confirm_author
from .book_views import get_title, confirm_book, title_only_search
from .isbn_views import get_book_by_isbn
from .location_views import (
    manage_locations,
    get_rooms,
    get_bookcases,
    get_shelves,
    assign_location,
    update_shelf_notes,
    shelve_books,
    get_shelf_details,
    reshelve_books,
    get_books_by_location,
    get_shelf_books
)
from .autocomplete_views import (
    author_autocomplete,
    title_autocomplete,
    test_autocomplete
)
from .list_views import list

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
    'list',
    'reshelve_books',
    'get_books_by_location',
    'get_shelf_books',
    'title_only_search',
]