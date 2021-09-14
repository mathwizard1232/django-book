import urllib.parse

from django.http import HttpResponseRedirect
from django.http.response import JsonResponse
from django.shortcuts import render

from olclient.openlibrary import OpenLibrary

from .forms import AuthorForm, ConfirmAuthorForm, TitleForm, TitleGivenAuthorForm, ConfirmBook
from .models import Author

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
        ol = OpenLibrary()
        author = ol.Author.search(name)[0]
        olid = author['key'][9:]  # remove "/authors/" prefix
        existing_author = Author.objects.filter(olid=olid).exists()
        form = ConfirmAuthorForm({'author_olid' :olid, 'author_name': author['name']})
        return render(request, 'confirm-author.html', {'form': form})
    if request.method == 'POST':
        # They have confirmed it if they are posting back. So then redirect them off to the title lookup
        name = request.POST['author_name']
        olid = request.POST['author_olid']
        return HttpResponseRedirect(f'/title.html?author_olid={olid}&author_name={name}')

def get_title(request):
    """ Do a lookup of a book by title, with a particular author potentially already set """
    if request.method == 'GET':
        if 'author_olid' in request.GET:
            form = TitleGivenAuthorForm({'author_olid': request.GET['author_olid'], 'author_name': request.GET['author_name']})
        else:
            form = TitleForm()
        return render(request, 'title.html', {'form': form})
    if request.method == 'POST':
        return HttpResponseRedirect(f"/confirm-book.html?title={request.POST['title']}&author_olid={request.POST['author_olid']}&author_name={request.POST['author_name']}")

def confirm_book(request):
    """ Given enough information for a lookup, retrieve the most likely book and confirm it's correct """
    if request.method == 'GET':
        if 'title' in request.GET:
            ol = OpenLibrary()
            title = request.GET['title']
            author = None  # search just on title if no author chosen
            title_args = {}
            if 'author_name' in request.GET:  # use author name as default if given; save in context
                author=request.GET['author_name']
                title_args['author_name'] = author
            if 'author_olid' in request.GET:  # prefer OpenLibrary ID if specified
                author=request.GET['author_olid']
                title_args['author_olid'] = author
            context = {'title_url': "title.html?" + urllib.parse.urlencode(title_args)}
            result = ol.Work.search(author=author, title=title)
            # TODO: This selects the first author, but should display multiple authors, or at least prefer the specified author
            context['form'] = ConfirmBook({'title': result.title, 'author_name': result.authors[0]['name'], 'work_olid': result.identifiers['olid'][0]})
            return render(request, 'confirm-book.html', context)
    
def author_autocomplete(request):
    """ Return a list of autocomplete suggestions for authors """
    # TODO: First attempt to select from authors already in library locally
    # TODO: Add ability to suggest authors with zero characters
    # TODO: Sort authors by number of books by them in the local library
    # Initial version: return the suggestions from OpenLibrary
    RESULTS_LIMIT = 5
    if 'q' in request.GET:
        ol = OpenLibrary()
        authors = ol.Author.search(request.GET['q'], RESULTS_LIMIT)
        names = [author['name'] for author in authors]
        return JsonResponse(names, safe=False)  # safe=False required to allow list rather than dict

def test_autocomplete(request):
    """ Test page from the bootstrap autocomplete repo to figure out how to get dropdowns working right """
    return render(request, 'test-autocomplete.html')
