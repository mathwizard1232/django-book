import logging
from django.http import HttpResponseBadRequest, JsonResponse
from ..models import Author, Book
from ..utils.ol_client import CachedOpenLibrary

logger = logging.getLogger(__name__)

# Constant used for separating values in autocomplete
DIVIDER = " ::: "

def author_autocomplete(request):
    """ Return a list of autocomplete suggestions for authors """
    # TODO: First attempt to select from authors already in library locally
    # TODO: Add ability to suggest authors with zero characters
    # TODO: Sort authors by number of books by them in the local library
    if not 'q' in request.GET:
        return JsonResponse({})
        
    search_str = request.GET['q']
    
    # first, look for local results
    author_qs = Author.objects.filter(search_name__contains=search_str)
    if author_qs:
        # Add any distinguishing details to local results
        results = []
        for author in author_qs:
            display_name = author.primary_name
            if hasattr(author, 'birth_date') and hasattr(author, 'death_date'):
                display_name += f" ({author.birth_date}-{author.death_date})"
            results.append(display_name + DIVIDER + author.olid)
        return JsonResponse(results, safe=False)

    # otherwise, do an OpenLibrary API search
    RESULTS_LIMIT = 5
    ol = CachedOpenLibrary()
    authors = ol.Author.search(search_str, RESULTS_LIMIT)
    
    # Enhanced display for OpenLibrary results
    results = []
    for author in authors:
        display_name = author['name']
        olid = author['key'].replace('/authors/', '')
        
        # Add birth/death dates if available
        if 'birth_date' in author and 'death_date' in author:
            display_name += f" ({author['birth_date']}-{author['death_date']})"
        
        # Add alternate names if available
        if 'alternate_names' in author:
            pen_names = [name for name in author['alternate_names'] if 'pseud.' in name]
            if pen_names:
                display_name += f" [also: {pen_names[0]}]"
                
        results.append(display_name + DIVIDER + olid)
        
    return JsonResponse(results, safe=False)

def title_autocomplete(request, oid):
    """
    Returns an autocomplete suggestion for the work
    Narrows down by author specified by oid
    """
    if 'q' not in request.GET:
        return HttpResponseBadRequest("q must be specified")

    # first attempt local lookup
    title = request.GET['q']
    author = Author.objects.get(olid=oid)
    book_qs = Book.objects.filter(author=author, search_name__contains=title)
    if book_qs:
        book = book_qs[0]
        logger.info("Successful local lookup of book candidate %s (%s) on %s", 
                   book.title, book.olid, title)
        # We're using the DIVIDER as a kludge to pass these two values together in a single value
        return JsonResponse(
            [book.title + DIVIDER + book.olid for book in book_qs],
            safe=False
        )

    # then try to do OpenLibrary API lookup
    ol = CachedOpenLibrary()    
    result = ol.Work.search(author=oid, title=title)
    if not result:
        logger.warning("Failed to lookup title autocomplete for author oid %s and title %s", 
                      oid, title)
        return JsonResponse({})
    names = [result.title]
    return JsonResponse(names, safe=False)

def test_autocomplete(request):
    """ Test page from the bootstrap autocomplete repo to figure out how to get dropdowns working right """
    from django.shortcuts import render
    return render(request, 'test-autocomplete.html')
