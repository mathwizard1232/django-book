from django.http import HttpResponseRedirect
from django.shortcuts import render

from olclient.openlibrary import OpenLibrary

from .forms import AuthorForm, ConfirmAuthorForm, TitleForm, TitleGivenAuthorForm
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
        form = ConfirmAuthorForm({'olid' :olid, 'author_name': author['name']})
        return render(request, 'confirm-author.html', {'form': form})
    if request.method == 'POST':
        # They have confirmed it if they are posting back. So then them off to the title lookup
        name = request.POST['author_name']
        olid = request.POST['olid']
        return HttpResponseRedirect(f'/title.html?olid={olid}&author_name={name}')

def get_title(request):
    """ Do a lookup of a book by title, with a particular author potentially already set """
    if request.method == 'GET':
        if 'olid' in request.GET:
            form = TitleGivenAuthorForm({'olid': request.GET['olid'], 'author_name': request.GET['author_name']})
        else:
            form = TitleForm()
        return render(request, 'title.html', {'form': form})

def confirm_book(request):
    """ Given enough information for a lookup, retrieve the most likely book and confirm it's correct """
    if request.method == 'GET':
        if 'title' in request.GET:
            if 'olid' in request.GET:
                pass  # TODO: got stuck here because found that OpenLibrary lookup is poor
            # Specifically: 13 results returned for "Stranger in a Strange Land", when should be unique
