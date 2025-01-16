"""book URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from .views import index, get_author, confirm_author, get_title, confirm_book, author_autocomplete, test_autocomplete, title_autocomplete, list, manage_locations, get_rooms, get_bookcases, get_shelves, assign_location, update_shelf_notes, shelve_books, get_shelf_details, get_book_by_isbn, reshelve_books, get_books_by_location, get_shelf_books, title_only_search
from .api_views import api_root

urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),
    path('author/', get_author, name='get_author'),
    path('confirm-author.html', confirm_author, name='confirm_author'),
    path('title.html', get_title, name='get_title'),
    path('confirm-book.html', confirm_book, name='confirm_book'),
    path('author-autocomplete', author_autocomplete, name='author_autocomplete'),
    path('author/<str:oid>/title-autocomplete', title_autocomplete, name='title_autocomplete'),
    path('test-autocomplete', test_autocomplete, name='test_autocomplete'),
    path('api/', api_root),
    path('list/', list, name='list'),
    path('locations/', manage_locations, name='manage_locations'),
    path('api/rooms/<int:location_id>/', get_rooms, name='get_rooms'),
    path('api/bookcases/<int:room_id>/', get_bookcases, name='get_bookcases'),
    path('api/shelves/<int:bookcase_id>/', get_shelves, name='get_shelves'),
    path('copy/<int:copy_id>/assign-location/', assign_location, name='assign_location'),
    path('api/shelves/<int:shelf_id>/update-notes/', update_shelf_notes, name='update_shelf_notes'),
    path('shelve-books/', shelve_books, name='shelve_books'),
    path('api/shelves/<int:shelf_id>/', get_shelf_details, name='get_shelf_details'),
    path('isbn/', get_book_by_isbn, name='get_book_by_isbn'),
    path('reshelve/', reshelve_books, name='reshelve_books'),
    path('api/books-by-location/<int:location_id>/', get_books_by_location, name='books_by_location'),
    path('api/shelves/<int:shelf_id>/books/', get_shelf_books, name='get_shelf_books'),
    path('api/shelf-details/<int:shelf_id>/', get_shelf_details, name='get_shelf_details'),
    path('title-only/', title_only_search, name='title_only'),
]
