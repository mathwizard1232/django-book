import json
import logging
import requests
from typing import List, Dict
from django.http import JsonResponse

from .models import Author, Book

logger = logging.getLogger(__name__)


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


def add_authors(authors):
    """Add entry for authors whose olid is not already present. No updates."""
    add_count = 0
    for author in authors:
        if not Author.objects.filter(olid=author["olid"]):
            Author.objects.create(olid=author["olid"], primary_name=author["primary_name"], search_name=author["search_name"])
            add_count += 1
    return add_count


def add_books(books):
    """Add entry for books whose olid is not already present. No updates."""
    add_count = 0
    for book in books:
        if not Book.objects.filter(olid=book["olid"]):
            author = Author.objects.get(olid=book["author_olid"])
            Book.objects.create(author=author, olid=book["olid"], title=book["title"], search_name=book["search_name"])
            add_count += 1
    return add_count

def add_to_library(new_data):
    """Add in any authors or books not previously present"""
    if "authors" in new_data:
        authors_added = add_authors(new_data["authors"])
    if "books" in new_data:
        books_added = add_books(new_data["books"])
    return {"authors_added": authors_added, "books_added": books_added}


def api_root(request):
    """Support basic GET and POST of whole library contents"""
    if request.method == "GET":
        return JsonResponse(get_library())
    if request.method == "POST":
        return JsonResponse(add_to_library(json.loads(request.body)))


def sync(remote):
    """
    POST local contents to remote, then GET on remote and add
    After, each will have a full set.
    """
    post_response = requests.post(remote, json=get_library())
    logger.info("Response to sync POST: " + post_response.content.decode('utf-8'))
    get_response = requests.get(remote)
    add_response = add_to_library(json.loads(get_response.content.decode('utf-8')))
    logger.info("Added from " + remote + ": " + json.dumps(add_response))

