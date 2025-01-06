import logging
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from ..forms import AuthorForm, ConfirmAuthorForm, ConfirmAuthorFormWithBio
from ..models import Author
from ..utils.ol_client import CachedOpenLibrary

logger = logging.getLogger(__name__)

def get_author(request):
    """ Render a form requesting author name, then redirect to confirmation of details """
    # Debug logging for request
    logger.info("GET params: %s", request.GET)
    logger.info("POST params: %s", request.POST)
    
    if request.method == 'POST':
        form = AuthorForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['author_name']
            author_role = request.POST.get('author_role', 'AUTHOR').upper()
            logger.info("POST processing - author_role: %s", author_role)
            return HttpResponseRedirect(f'/confirm-author.html?author_name={name}&author_role={author_role}')
    
    author_role = request.GET.get('author_role', 'AUTHOR').upper()
    logger.info("GET processing - author_role: %s", author_role)
    form = AuthorForm()
    
    context = {
        'form': form,
        'is_editor': author_role == 'EDITOR',
        'author_role': author_role
    }
    logger.info("Rendering template with context: %s", context)
    return render(request, 'author.html', context)

def confirm_author(request):
    """ Do a lookup of this author by the name sent and display and confirm details from OpenLibrary """
    if request.method == 'GET':
        name = request.GET['author_name']
        author_role = request.GET.get('author_role', 'AUTHOR')
        
        if DIVIDER in name:
            # This is an autocomplete result already known locally
            name, olid = name.split(DIVIDER)
            return HttpResponseRedirect(f'/title.html?author_olid={olid}&author_name={name}&author_role={author_role}')
            
        ol = CachedOpenLibrary()
        results = ol.Author.search(name, 2)
        if not results:
            return HttpResponseRedirect('/author')  # If we get a bad request, just have them try again
        
        first_author = results[0]
        first_olid = first_author['key'][9:]  # remove "/authors/" prefix
        first_author_full = ol.Author.get(first_olid)
        logger.info("First author full details: %s", vars(first_author_full))
        bio = first_author_full.bio
        
        logger.info("Author bio for %s: %s", first_author['name'], bio if bio else "No biography available")
        
        form = ConfirmAuthorForm({
            'author_olid': first_olid, 
            'author_name': first_author['name'], 
            'search_name': name,
            'author_role': author_role
        })

        if bio:
            form = ConfirmAuthorFormWithBio({
                'author_olid': first_olid,
                'author_name': first_author['name'],
                'search_name': name,
                'bio': bio
            })

        form2 = None
        if len(results) > 1:
            # NOTE: adding this because sometimes even with full name first result is wrong
            second_author = results[1]
            second_olid = second_author['key'][9:]
            second_author_full = ol.Author.get(second_olid)
            logger.info("Second author full details: %s", vars(second_author_full))
            second_bio = second_author_full.bio
            form2 = ConfirmAuthorForm({
                'author_olid': second_olid,
                'author_name': second_author['name'],
                'search_name': name
            })
            if second_bio:
                form2 = ConfirmAuthorFormWithBio({
                    'author_olid': second_olid,
                    'author_name': second_author['name'],
                    'search_name': name,
                    'bio': second_bio
                })
        return render(request, 'confirm-author.html', {'form': form, 'form2': form2})

    if request.method == 'POST':
        # Get the author role from the form
        author_role = request.POST.get('author_role', 'AUTHOR')
        
        # This is a confirmed author. Ensure that they have been recorded.
        name = request.POST['author_name']
        olid = request.POST['author_olid']
        search_name = request.POST['search_name']

        author_lookup_qs = Author.objects.filter(olid=olid)
        if not author_lookup_qs:
            author = Author.objects.create(
                olid=olid,
                primary_name=name,
                search_name=search_name,
            )
            logger.info("Recorded new author: %s (%s) AKA %s)", name, olid, search_name)

        # Finally, redirect them off to the title lookup
        return HttpResponseRedirect(f'/title.html?author_olid={olid}&author_name={name}&author_role={author_role}')
