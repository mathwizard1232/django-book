import logging
import urllib.parse

from django import forms
from django.http import HttpResponseRedirect
from django.http.response import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render

from olclient.openlibrary import OpenLibrary

from .forms import AuthorForm, ConfirmAuthorForm, ConfirmAuthorFormWithBio, TitleForm, TitleGivenAuthorForm, ConfirmBook
from .models import Author, Book

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
        ol = OpenLibrary()
        results = ol.Author.search(name, 2)
        if not results:
            return HttpResponseRedirect('/author')  # If we get a bad request, just have them try again
        first_author = results[0]
        first_olid = first_author['key'][9:]  # remove "/authors/" prefix
        bio = ol.Author.get(first_olid).bio
        
        form = ConfirmAuthorForm({'author_olid' :first_olid, 'author_name': first_author['name'], 'search_name': name})

        if bio:
            form = ConfirmAuthorFormWithBio({'author_olid' :first_olid, 'author_name': first_author['name'], 'search_name': name, 'bio': bio})
        form2 = None
        if len(results) > 1:
            # NOTE: adding this because sometimes even with full name first result is wrong
            second_author = results[1]
            second_olid = second_author['key'][9:]
            second_bio = ol.Author.get(second_olid).bio
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
    ol = OpenLibrary()
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
    result = ol.Work.search(author=author, title=search_title)

    if not result:
        # try searching just for title then, maybe wrong author selection
        result = ol.Work.search(title=search_title)
        if not result:
            # TODO: better handling
            raise Exception("no result")
        
    display_title = result.title
    work_olid = result.identifiers['olid'][0]
    publish_year = result.publish_date
    publisher = result.publisher

    # TODO: This selects the first author, but should display multiple authors, or at least prefer the specified author
    author_name = result.authors[0]['name']

    # This block is setting up the context and form to display the book
    args['title'] = display_title
    args['work_olid'] = work_olid
    args['publisher'] = publisher
    args['publish_year'] = publish_year
    context['form'] = ConfirmBook(args)
    context['author_name'] = author_name

    # Display confirmation form, or
    if request.method == 'GET':
        return render(request, 'confirm-book.html', context)
    # Process confirmation and direct to next step
    elif request.method == 'POST':
        # If we don't have a record of this Book yet, record it now.
        book_qs = Book.objects.filter(olid = work_olid)
        if not book_qs:
            assert author_olid  # We shouldn't hit this point without having done a proper Author lookup
            Book.objects.create(
                olid = work_olid,
                author = Author.objects.get(olid=author_olid),
                title = display_title,
                search_name = search_title,
            )
            logger.info("Added new Book %s (%s) AKA %s", display_title, work_olid, search_title)
        return render(request, 'just-entered-book.html', context)

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
    ol = OpenLibrary()
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
    ol = OpenLibrary()    
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
    """ Display summary of what's in library, (or search results eventually) """
    authors = Author.objects.all()
    books = Book.objects.all()
    context={'authors': authors, 'books': books}
    return render(request, 'list.html', context)
