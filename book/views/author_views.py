import logging
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from ..forms import AuthorForm, ConfirmAuthorForm, ConfirmAuthorFormWithBio
from ..models import Author
from ..utils.ol_client import CachedOpenLibrary
from .autocomplete_views import DIVIDER  # Import the DIVIDER from autocomplete_views
from django.views.decorators.http import require_GET

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
            
            # Check if this is an autocomplete result with DIVIDER
            if DIVIDER in name:
                # This is a local author result, extract name and olid
                name, olid = name.split(DIVIDER)
                return HttpResponseRedirect(f'/title.html?author_olid={olid}&author_name={name}&author_role={author_role}')
            
            # For OpenLibrary results, redirect to confirmation
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

def sort_authors_by_quality(authors):
    """
    Sort authors by quality metrics in this order:
    1. High work count (>100)
    2. Has birth/death dates
    3. Has subjects
    4. Raw work count
    """
    def author_quality_score(author):
        score = 0
        # High work count is most important
        work_count = author.get('work_count', 0)
        if work_count > 100:
            score += 1000
        
        # Having biographical data is next most important
        if author.get('birth_date') or author.get('death_date'):
            score += 500
            
        # Having subjects suggests a well-documented author
        if author.get('subjects'):
            score += len(author.get('subjects', []))
            
        # Finally, use raw work count as a tiebreaker
        score += work_count
        
        return score
    
    return sorted(authors, key=author_quality_score, reverse=True)

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
        response = ol.Author.search(name, limit=5)  # Get more results to sort from
        logger.info("Initial search response: %s", response)
        
        # Extract docs array from response
        authors = response.get('docs', []) if isinstance(response, dict) else response
        logger.info("Authors from response: %s", authors)
        
        # Sort by quality and take top 2
        authors = sort_authors_by_quality(authors)
        logger.info("Sorted results: %s", authors)
        authors = authors[:2]
        logger.info("Top 2 results: %s", authors)
        
        if not authors:
            return HttpResponseRedirect('/author')  # If we get a bad request, just have them try again
        
        first_author = authors[0]
        first_olid = first_author['key'][9:]  # remove "/authors/" prefix
        first_author_full = ol.Author.get(first_olid)
        logger.info("First author full details: %s", first_author_full)
        
        # Enhanced author details
        first_author_details = {
            'author_olid': first_olid,
            'author_name': first_author['name'],
            'search_name': name,
            'author_role': author_role,
            'birth_date': first_author_full.get('birth_date', ''),
            'death_date': first_author_full.get('death_date', ''),
            'alternate_names': first_author_full.get('alternate_names', []),
            'personal_name': first_author_full.get('personal_name', ''),
            'bio': first_author_full.get('bio', ''),
            'work_count': first_author.get('work_count', 0)
        }
        logger.info("First author details for template: %s", first_author_details)
        
        form = ConfirmAuthorFormWithBio(first_author_details) if first_author_details['bio'] else ConfirmAuthorForm(first_author_details)

        form2 = None
        second_author_details = None  # Initialize to None by default
        if len(authors) > 1:
            second_author = authors[1]
            second_olid = second_author['key'][9:]
            second_author_full = ol.Author.get(second_olid)
            logger.info("Second author full details: %s", second_author_full)
            
            # Enhanced second author details
            second_author_details = {
                'author_olid': second_olid,
                'author_name': second_author['name'],
                'search_name': name,
                'author_role': author_role,
                'birth_date': second_author_full.get('birth_date', ''),
                'death_date': second_author_full.get('death_date', ''),
                'alternate_names': second_author_full.get('alternate_names', []),
                'personal_name': second_author_full.get('personal_name', ''),
                'bio': second_author_full.get('bio', ''),
                'work_count': second_author.get('work_count', 0)
            }
            logger.info("Second author details for template: %s", second_author_details)
            
            form2 = ConfirmAuthorFormWithBio(second_author_details) if second_author_details['bio'] else ConfirmAuthorForm(second_author_details)

        context = {
            'form': form, 
            'form2': form2,
            'first_author_details': first_author_details,
            'second_author_details': second_author_details
        }
        logger.info("Rendering template with context: %s", context)
        return render(request, 'confirm-author.html', context)

    if request.method == 'POST':
        # Get the author role from the form
        author_role = request.POST.get('author_role', 'AUTHOR')
        
        # This is a confirmed author. Ensure that they have been recorded.
        name = request.POST['author_name']
        olid = request.POST['author_olid']
        search_name = request.POST['search_name']

        author_lookup_qs = Author.objects.filter(olid=olid)
        if not author_lookup_qs:
            # Get full author details from OpenLibrary for creation
            ol = CachedOpenLibrary()
            author_full = ol.Author.get(olid)
            
            author = Author.objects.create(
                olid=olid,
                primary_name=name,
                search_name=search_name,
                birth_date=author_full.get('birth_date', ''),
                death_date=author_full.get('death_date', ''),
                alternate_names=author_full.get('alternate_names', [])
            )
            logger.info("Recorded new author: %s (%s) AKA %s)", name, olid, search_name)

        # Redirect to title lookup
        return HttpResponseRedirect(f'/title.html?author_olid={olid}&author_name={name}&author_role={author_role}')

"""@require_GET
def search_author(request):
    Search for an author by name.
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse([], safe=False)

    # First search local database
    local_authors = Author.objects.filter(search_name__icontains=query.lower())
    results = []
    
    # Add local results
    for author in local_authors:
        results.append({
            'name': author.primary_name,
            'birth_date': author.birth_date,
            'death_date': author.death_date,
            'value': f"{author.primary_name}{DIVIDER}{author.olid}"
        })

    # Then search OpenLibrary if needed
    if len(results) < 5:
        ol = CachedOpenLibrary()
        ol_results = ol.Author.search(query, limit=5-len(results))
        
        # Add OpenLibrary results
        for author in ol_results:
            if author.get('key'):
                results.append({
                    'name': author.get('name', ''),
                    'alternate_names': author.get('alternate_names', []),
                    'birth_date': author.get('birth_date', ''),
                    'death_date': author.get('death_date', ''),
                    'key': author['key'],
                    'type': author.get('type', {}).get('key', '')
                })

    print(f"Search results for '{query}':", results)  # Debug log
    return JsonResponse(results, safe=False)
"""