import logging
from django.shortcuts import render
from django.http import HttpResponseRedirect
from ..forms import ISBNForm, ConfirmBook
from ..models import Location
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
                    # Prepare form data for confirmation
                    form_data = {
                        'title': book.title,
                        'work_olid': book.identifiers['olid'][0],
                        'publisher': book.publisher,
                        'publish_year': book.publish_date
                    }
                    
                    # Add author info if available
                    if book.authors:
                        author = book.authors[0]  # author is now a dict
                        form_data['author_name'] = author['name']
                        if 'olid' in author:
                            form_data['author_olid'] = author['olid']
                    
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
