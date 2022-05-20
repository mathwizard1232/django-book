import json
from typing import List, Dict
from django.http import JsonResponse

from .models import Author, Book

def get_authors() -> List:
    authors = Author.objects.all()
    results = []
    for author in authors:
        results.append({"olid": author.olid, "primary_name": author.primary_name, "search_name": author.search_name})
    return results


def get_books() -> List:
    books = Book.objects.all()
    results = []
    for book in books:
        results.append(
            {"author_olid": book.author.olid, 
            "title": book.title, 
            "search_name": book.search_name, 
            "olid": book.olid}
        )
    return results

def get_library() -> Dict:
    """Return a JSON view of the library"""
    results = {}
    results['authors'] = get_authors()
    results['books'] = get_books()
    return results


def add_to_library(new_data):
    """Add in any authors or books not previously present"""
    raise NotImplementedException()


def api_root(request):
    """Support basic GET and POST of whole library contents"""
    if request.method == "GET":
        return JsonResponse(get_library())
    if request.method == "POST":
        return JsonResponse(add_to_library(json.loads(request.body)))
