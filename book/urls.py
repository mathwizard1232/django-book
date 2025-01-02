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

from .views import index, get_author, confirm_author, get_title, confirm_book, author_autocomplete, test_autocomplete, title_autocomplete, list, manage_locations, get_rooms, get_bookcases, get_shelves, assign_location
from .api_views import api_root

urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),
    path('author/', get_author),
    path('confirm-author.html', confirm_author),
    path('title.html', get_title),
    path('confirm-book.html', confirm_book),
    path('author-autocomplete', author_autocomplete),
    path('author/<str:oid>/title-autocomplete', title_autocomplete),
    path('test-autocomplete', test_autocomplete),
    path('api/', api_root),
    path('list/', list),
    path('locations/', manage_locations, name='manage_locations'),
    path('api/rooms/<int:location_id>/', get_rooms, name='get_rooms'),
    path('api/bookcases/<int:room_id>/', get_bookcases, name='get_bookcases'),
    path('api/shelves/<int:bookcase_id>/', get_shelves, name='get_shelves'),
    path('copy/<int:copy_id>/assign-location/', assign_location, name='assign_location'),
]
