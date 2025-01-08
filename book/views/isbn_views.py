import logging
from django.shortcuts import render
from django.http import HttpResponseRedirect
from ..forms import ISBNForm, ConfirmBook
from ..models import Location, Work
from ..utils.ol_client import CachedOpenLibrary

logger = logging.getLogger(__name__)

def get_book_by_isbn(request):
    """Handle ISBN lookup form submission"""
    if request.method == 'POST':
        form = ISBNForm(request.POST)
        if form.is_valid():
            isbn = form.cleaned_data['isbn']
            try:
                ol = CachedOpenLibrary()
                book = ol.Work.search_by_isbn(isbn)
                
                if book:
                    work_olid = book.identifiers['olid'][0]
                    
                    # Check for existing work with copies
                    existing_work = Work.objects.filter(olid=work_olid).first()
                    if existing_work and existing_work.edition_set.filter(copy__isnull=False).exists():
                        # Prepare form data for duplicate confirmation
                        form_data = {
                            'title': book.title,
                            'work_olid': work_olid,
                            'publisher': book.publisher,
                            'publish_year': book.publish_date
                        }
                        
                        # Handle author data
                        if book.authors:
                            author_olids = []
                            author_names = []
                            for author in book.authors:
                                author_names.append(author['name'])
                                if 'olid' in author:
                                    author_olids.append(author['olid'])
                            
                            form_data['author_olids'] = ','.join(author_olids)
                            form_data['author_names'] = ','.join(author_names)
                        
                        context = {
                            'work': existing_work,
                            'form_data': form_data,
                            'locations': Location.objects.all()
                        }
                        return render(request, 'confirm-duplicate.html', context)
                    
                    # Prepare form data for confirmation
                    form_data = {
                        'title': book.title,
                        'work_olid': book.identifiers['olid'][0],
                        'publisher': book.publisher,
                        'publish_year': book.publish_date
                    }
                    
                    # Handle multiple authors
                    if book.authors:
                        author_olids = []
                        author_names = []
                        
                        for author in book.authors:
                            author_name = author['name']
                            author_names.append(author_name)
                            
                            # If we have an OLID, use it directly
                            if 'olid' in author:
                                author_olids.append(author['olid'])
                                logger.info("Using direct author OLID from ISBN lookup: %s for %s", 
                                          author['olid'], author_name)
                            else:
                                # Try to search for author by name to get OLID
                                try:
                                    author_results = ol.Author.search(author_name)
                                    if author_results:
                                        # Get the OLID from the key (removing "/authors/" prefix)
                                        author_key = author_results[0]['key']
                                        author_olid = author_key[9:] if author_key.startswith('/authors/') else author_key
                                        author_olids.append(author_olid)
                                        logger.info("Found author OLID via search: %s for %s", 
                                                  author_olid, author_name)
                                    else:
                                        logger.warning("No author results found for name: %s", author_name)
                                except Exception as e:
                                    logger.warning("Failed to find author OLID: %s", e)
                                    # Continue without author OLID - will need manual author selection
                        
                        form_data['author_olids'] = ','.join(author_olids)
                        form_data['author_names'] = ','.join(author_names)
                    
                    logger.info("Final form_data for confirmation: %s", form_data)
                    
                    confirm_form = ConfirmBook(form_data)
                    return render(request, 'confirm-book.html', {
                        'forms': [confirm_form],
                        'locations': Location.objects.all()
                    })
                else:
                    form.add_error('isbn', 'No book found with this ISBN')
            except Exception as e:
                logger.exception("Error searching by ISBN")
                form.add_error('isbn', f'Error looking up ISBN: {str(e)}')
    else:
        form = ISBNForm()
    
    return render(request, 'isbn.html', {'form': form})
