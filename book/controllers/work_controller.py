from typing import Dict, List, Optional, Tuple
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponseBadRequest, HttpResponseServerError
import logging
import urllib.parse
import json

from ..models import Work, Author, Edition, Copy, Shelf, Location
from ..utils.ol_client import CachedOpenLibrary

logger = logging.getLogger(__name__)

class WorkController:
    def __init__(self, request):
        logger.info("=== Initializing WorkController ===")
        logger.info("Request method: %s", request.method)
        logger.info("POST data: %s", dict(request.POST))
        logger.info("GET data: %s", dict(request.GET))
        self.request = request
        self.ol_client = CachedOpenLibrary()
        
    def handle_book_confirmation(self) -> HttpResponse:
        """Process the confirmed book selection and create local records"""
        try:
            logger.info("=== Starting handle_book_confirmation ===")
            
            # Log request context
            self._log_request_context()
            
            # Check if this is a collection confirmation
            if self.request.POST.get('second_work_title'):
                logger.info("=== Collection Flow Details ===")
                logger.info("First work title: %s", self.request.POST.get('first_work_title'))
                logger.info("Second work title: %s", self.request.POST.get('second_work_title'))
                logger.info("Collection title: %s", self.request.POST.get('title'))
                return self._handle_collection_confirmation()
                
            # Early returns for single work flow
            if not self.request.POST.get('work_olid'):
                logger.error("No work_olid found in POST data")
                return HttpResponseBadRequest('work_olid required')
                
            # Get basic work data
            work_data = self._get_work_data()
            if not work_data:
                logger.error("Could not fetch work data")
                return HttpResponseBadRequest('Could not fetch work data')
                
            # Check for existing work with copies
            existing_work = self._check_existing_work()
            if existing_work:
                logger.info("Found existing work with copies")
                return existing_work
                
            # Process authors
            logger.info("Processing authors")
            authors, editors = self._process_authors(work_data)
            
            # Create or get work
            logger.info("Creating or getting work")
            work = self._create_or_get_work(authors, editors)
            
            # Handle editions and copies
            logger.info("Handling editions and copies")
            message = self._handle_editions_and_copies(work)
            
            logger.info("Redirecting with message: %s", message)
            return HttpResponseRedirect(f'/author/?message={message}')
        except Exception as e:
            logger.exception("=== CRITICAL ERROR in handle_book_confirmation ===")
            logger.error("Error details: %s", str(e))
            logger.error("Request POST data: %s", dict(self.request.POST))
            logger.error("Request GET data: %s", dict(self.request.GET))
            raise  # Re-raise the exception to maintain error visibility
        
    def _log_request_context(self) -> None:
        """Log detailed request information"""
        logger.info("=== Book Confirmation Request Details ===")
        logger.info("POST data: %s", dict(self.request.POST))
        logger.info("GET data: %s", dict(self.request.GET))

    def _get_work_data(self) -> Optional[Dict]:
        """Fetch and return work data from OpenLibrary"""
        work_olid = self.request.POST.get('work_olid')
        try:
            work = self.ol_client.Work.get(work_olid)
            logger.info("Found OpenLibrary work: %s", work)
            return work
        except Exception as e:
            logger.warning(f"Error getting work details from OpenLibrary: {e}")
            return None
            
    def _check_existing_work(self) -> Optional[HttpResponse]:
        """Check if work exists and has copies, return confirmation page if needed"""
        work_olid = self.request.POST.get('work_olid')
        existing_work = Work.objects.filter(olid=work_olid).first()
        
        if existing_work and existing_work.edition_set.filter(copy__isnull=False).exists():
            if self.request.POST.get('confirm_duplicate') != 'true':
                context = {
                    'work': existing_work,
                    'form_data': self.request.POST,
                    'locations': Location.objects.all()
                }
                return render(self.request, 'confirm-duplicate.html', context)
        return None 

    def _process_authors(self, work_data: Dict) -> Tuple[List[Author], List[Author]]:
        """Process and return authors and editors from work data"""
        authors = []
        editors = []
        
        # Get author names and OLIDs from the form
        author_names = self.request.POST.get('author_names', '').split(',')
        author_olids = self.request.POST.get('author_olids', '').split(',')
        author_olids = [olid for olid in author_olids if olid]
        
        logger.info("Processing authors with names: %s and OLIDs: %s", author_names, author_olids)
        
        # Parse author roles
        try:
            author_roles = json.loads(self.request.POST.get('author_roles', '{}'))
            logger.info("Author roles: %s", author_roles)
        except json.JSONDecodeError:
            logger.warning("Could not parse author_roles JSON")
            author_roles = {}
            
        # Check for selected author from form
        selected_author = None
        selected_olid = self.request.POST.get('selected_author_olid')
        
        if selected_olid:
            selected_author = Author.objects.filter(olid=selected_olid).first()
            logger.info("Found selected author: %s with OLID: %s", selected_author, selected_olid)
        
        # Process each author
        for olid in author_olids or [None]:  # Handle case where author_olids is empty
            logger.info("Processing author with OLID: %s", olid)
            author = self._get_or_create_author(
                olid=olid,
                selected_author=selected_author,
                author_names=author_names,
                author_roles=author_roles,
                work_data=work_data
            )
            logger.info("Got author from _get_or_create_author: %s", author)
            
            if author:
                # Update alternate names from work data if available
                logger.info("Checking work_data for alternate names: %s", work_data)
                if hasattr(work_data, 'author_alternative_name'):
                    logger.info("Found author_alternative_name: %s", work_data.author_alternative_name)
                    if not author.alternate_names:
                        author.alternate_names = []
                    for alt_name in work_data.author_alternative_name:
                        if alt_name not in author.alternate_names:
                            author.alternate_names.append(alt_name)
                            logger.info("Added alternate name: %s", alt_name)
                    author.save()
                    logger.info("Updated author alternate names: %s", author.alternate_names)
                else:
                    logger.info("No author_alternative_name found in work_data")

                if author_roles.get(author.primary_name, 'AUTHOR') == 'AUTHOR':
                    authors.append(author)
                    logger.info("Added as author: %s", author)
                else:
                    editors.append(author)
                    logger.info("Added as editor: %s", author)
        
        logger.info("Final authors list: %s", authors)
        logger.info("Final editors list: %s", editors)
        return authors, editors
        
    def _get_or_create_author(self, olid: str, selected_author: Optional[Author], 
                             author_names: List[str], author_roles: Dict[str, str],
                             work_data: Dict) -> Optional[Author]:
        """Get existing author or create new one with proper name formatting"""
        logger.info("=== Starting _get_or_create_author ===")
        logger.info("Input - OLID: %s, Names: %s, Roles: %s", olid, author_names, author_roles)
        
        # If we have a selected author, update and return it
        if selected_author:
            logger.info("Using selected author: %s", selected_author.primary_name)
            try:
                author_details = self.ol_client.Author.get(olid)
                if author_details:
                    logger.info("Updating selected author with details: %s", author_details)
                    self._update_author_details(selected_author, author_details)
                return selected_author
            except Exception as e:
                logger.warning(f"Error getting author details: {e}")
                return selected_author
                
        # Try to find existing author by OLID first
        author = Author.objects.filter(olid=olid).first()
        if author:
            logger.info("Found author by OLID: %s", author.primary_name)
            return author

        # Try to match by name or alternate names
        for name in author_names:
            name_lower = name.lower()
            logger.info("Checking for name match: %s", name)
            for local_author in Author.objects.all():
                logger.info("Comparing with local author: %s (search_name: %s, alternates: %s)", 
                           local_author.primary_name, local_author.search_name, 
                           local_author.alternate_names)
                
                # Check primary name and alternate names
                if (local_author.search_name == name_lower):
                    logger.info("Found match by primary name")
                    matched = True
                elif (local_author.alternate_names and 
                      name_lower in [alt.lower() for alt in local_author.alternate_names]):
                    logger.info("Found match by alternate name")
                    matched = True
                else:
                    matched = False
                    
                if matched:
                    logger.info("Found author match: %s matches %s", name, local_author.primary_name)
                    try:
                        author_details = self.ol_client.Author.get(olid)
                        if author_details:
                            logger.info("Updating matched author with details: %s", author_details)
                            self._update_author_details(local_author, author_details)
                    except Exception as e:
                        logger.warning(f"Error updating author details: {e}")
                    return local_author

        # Create new author if no match found
        logger.info("No existing author found, attempting creation")
        for name in author_names:
            if author_roles.get(name) == "AUTHOR":
                logger.info("Creating new author with name: %s", name)
                try:
                    author_details = self.ol_client.Author.get(olid)
                    if author_details:
                        logger.info("Creating author with details: %s", author_details)
                        return self._create_author_with_details(name, olid, author_details)
                except Exception as e:
                    logger.warning(f"Error getting author details: {e}")
                    # Fall back to basic author creation
                    logger.info("Falling back to basic author creation")
                    return Author.objects.create(
                        primary_name=name,
                        search_name=name.lower(),
                        olid=olid
                    )

        logger.info("No author created - returning None")
        return None
        
    def _update_author_details(self, author: Author, author_details: Dict) -> None:
        """Update author with details from OpenLibrary"""
        logger.info("=== Updating Author Details ===")
        logger.info("Current author state - primary: %s, search: %s", author.primary_name, author.search_name)
        logger.info("Author details from OL: %s", author_details)
        
        alternate_names = author_details.get('alternate_names', [])
        real_name = author_details.get('personal_name') or author_details.get('name')
        
        if real_name:
            # Use the current primary name as the pen name
            pen_name = author.primary_name
            # Keep the original search name
            search_name = author.search_name
            logger.info("Processing names - real: %s, pen: %s, search: %s", real_name, pen_name, search_name)
            
            # Check if current name is in alternate names list
            if pen_name not in alternate_names:
                alternate_names.append(pen_name)
            
            formatted_name = self._format_pen_name(real_name, pen_name, alternate_names)
            logger.info("Final formatted name: %s", formatted_name)
            
            author.primary_name = formatted_name
            author.search_name = search_name  # Keep existing search name
            author.alternate_names = alternate_names
            author.save()
            logger.info("Updated author state - primary: %s, search: %s", author.primary_name, author.search_name)
        
    def _create_author_with_details(self, name: str, olid: str, author_details: Dict) -> Author:
        """Create new author with OpenLibrary details"""
        logger.info("=== Creating Author with Details ===")
        logger.info("Initial name: %s, OLID: %s", name, olid)
        logger.info("Author details from OL: %s", author_details)
        
        alternate_names = author_details.get('alternate_names', [])
        real_name = author_details.get('personal_name') or author_details.get('name')
        
        # Always use the original search name
        search_name = name.lower()
        logger.info("Original search name: %s", search_name)
        
        if real_name and real_name != name:  # If we have a real name different from search name
            # The searched name (name) is the pen name since user searched for it
            pen_name = name
            logger.info("Processing names - real: %s, pen: %s", real_name, pen_name)
            
            # Add pen name to alternate names if not present
            if pen_name not in alternate_names:
                alternate_names.append(pen_name)
            
            formatted_name = self._format_pen_name(real_name, pen_name, alternate_names)
        else:
            formatted_name = name
        
        logger.info("Final names - formatted: %s, search: %s", formatted_name, search_name)
        
        return Author.objects.create(
            primary_name=formatted_name,
            search_name=search_name,  # Use original search name
            olid=olid,
            alternate_names=alternate_names
        )
        
    def _format_pen_name(self, real_name: str, pen_name: str, alternate_names: List[str]) -> str:
        """Format author name to include pen name if appropriate"""
        logger.info(f"Formatting pen name - real: {real_name}, pen: {pen_name}, alternates: {alternate_names}")
        
        # Split both names into components
        real_parts = real_name.split()
        pen_parts = pen_name.split()
        
        # Check if first and last names already match
        if len(real_parts) >= 2 and len(pen_parts) >= 2:
            if real_parts[0] == pen_parts[0] and real_parts[-1] == pen_parts[-1]:
                logger.error(
                    "CRITICAL: Attempted to double-format pen name!"
                    f"\nExisting name: {real_name}"
                    f"\nPen name to add: {pen_name}"
                    f"\nFirst/last match detected"
                    f"\nAlternate names: {alternate_names}",
                    stack_info=True
                )
                # Kludge fix; better would be to prevent hitting this perhaps.
                return pen_name

        # If the pen name is in alternate names, it confirms it's a valid pen name
        if pen_name.lower() in [alt.lower() for alt in alternate_names]:
            # Split real name into components
            name_parts = real_name.split()
            if len(name_parts) >= 2:
                real_first = name_parts[0]
                real_last = name_parts[-1]
                formatted = f"{real_first} '{pen_name}' {real_last}"
                logger.info(f"Formatted with pen name: {formatted}")
                return formatted
        
        logger.info(f"Using real name: {real_name}")
        return real_name

    def _create_or_get_work(self, authors: List[Author], editors: List[Author]) -> Work:
        """Create new work or get existing one and update its relationships"""
        work_olid = self.request.POST.get('work_olid')
        display_title = self.request.POST.get('title')
        clean_title = Work.strip_volume_number(display_title)
        search_name = clean_title.lower()
        
        # Check for existing work
        work = Work.objects.filter(olid=work_olid).first()
        if work:
            # Update existing work's authors/editors
            work.authors.clear()
            work.editors.clear()
            for author in authors:
                work.authors.add(author)
            for editor in editors:
                work.editors.add(editor)
            return work
            
        # Handle multivolume works
        is_multivolume = self.request.POST.get('is_multivolume') == 'on'
        entry_type = self.request.POST.get('entry_type')
        volume_number = self.request.POST.get('volume_number')
        volume_count = self.request.POST.get('volume_count')
        
        if is_multivolume:
            return self._create_multivolume_work(
                clean_title=clean_title,
                search_name=search_name,
                authors=authors,
                editors=editors,
                entry_type=entry_type,
                volume_number=volume_number,
                volume_count=volume_count
            )
            
        # Create single volume work
        work = Work.objects.create(
            olid=work_olid,
            title=clean_title,
            search_name=search_name,
            type='NOVEL'
        )
        # Add authors and editors after creation
        for author in authors:
            work.authors.add(author)
        for editor in editors:
            work.editors.add(editor)
        return work
        
    def _create_multivolume_work(self, clean_title: str, search_name: str,
                                authors: List[Author], editors: List[Author],
                                entry_type: str, volume_number: Optional[str],
                                volume_count: Optional[str]) -> Work:
        """Handle creation of multivolume works based on entry type"""
        work_olid = self.request.POST.get('work_olid')
        
        if entry_type == 'COMPLETE':
            work, volumes = Work.create_volume_set(
                title=clean_title,
                volume_count=int(volume_count),
                authors=authors,
                editors=editors,
                olid=work_olid,
                search_name=search_name,
                type='NOVEL'
            )
        elif entry_type == 'SINGLE':
            work, volume = Work.create_single_volume(
                set_title=clean_title,
                volume_number=int(volume_number) if volume_number else 1,
                authors=authors,
                editors=editors,
                olid=work_olid,
                search_name=search_name,
                type='NOVEL'
            )
            volumes = [volume]
        else:  # PARTIAL
            volume_numbers = [int(v) for v in self.request.POST.get('volume_numbers', '').split(',') if v]
            work, volumes = Work.create_partial_volume_set(
                title=clean_title,
                volume_numbers=volume_numbers,
                authors=authors,
                editors=editors,
                olid=work_olid,
                search_name=search_name,
                type='NOVEL'
            )
            
        # Create editions and copies for all volumes
        for volume in volumes:
            self._create_edition_and_copy(volume)
            
        return work
        
    def _create_edition_and_copy(self, work: Work) -> Tuple[Edition, Copy]:
        """Create edition and copy for a work, with optional shelving"""
        publisher = self.request.POST.get('publisher', 'Unknown')
        action = self.request.POST.get('action', 'Confirm Without Shelving')
        
        edition = Edition.objects.create(
            work=work,
            publisher=publisher,
            format="PAPERBACK"
        )
        
        copy_data = {
            'edition': edition,
            'condition': "GOOD"
        }
        
        if action == 'Confirm and Shelve':
            shelf_id = self.request.POST.get('shelf')
            if shelf_id:
                shelf = Shelf.objects.get(id=shelf_id)
                copy_data.update({
                    'shelf': shelf,
                    'location': shelf.bookcase.get_location(),
                    'room': shelf.bookcase.room,
                    'bookcase': shelf.bookcase
                })
                
        copy = Copy.objects.create(**copy_data)
        return edition, copy
        
    def _handle_editions_and_copies(self, work: Work) -> str:
        """Create editions and copies for the work and return appropriate message"""
        display_title = self.request.POST.get('title')
        action = self.request.POST.get('action', 'Confirm Without Shelving')
        
        if not work.is_multivolume:
            edition, copy = self._create_edition_and_copy(work)
            
        # Format the response message
        if action == 'Confirm and Shelve' and copy.shelf:
            location_path = (f"{copy.location.name} > {copy.room.name} > "
                           f"{copy.bookcase.name} > Shelf {copy.shelf.position}")
            message = f"new_copy_shelved&title={urllib.parse.quote(display_title)}&location={urllib.parse.quote(location_path)}"
        else:
            message = f"new_work&title={urllib.parse.quote(display_title)}"
            
        return message 

    def _handle_collection_confirmation(self) -> HttpResponse:
        """Handle the confirmation of a collection of works"""
        logger.info("=== Starting Collection Confirmation ===")
        
        # Get both works' details from POST data
        first_work = {
            'title': self.request.POST.get('first_work_title'),
            'olid': self.request.POST.get('first_work_olid'),
            'author_names': self.request.POST.get('first_work_author_names', '').split(','),
            'author_olids': self.request.POST.get('first_work_author_olids', '').split(','),
        }

        logger.info("First work: %s", first_work)
        
        second_work = {
            'title': self.request.POST.get('second_work_title'),
            'olid': self.request.POST.get('second_work_olid'),
            'author_names': self.request.POST.get('second_work_author_names', '').split(','),
            'author_olids': self.request.POST.get('second_work_author_olids', '').split(','),
        }
        
        logger.info("Second work: %s", second_work)
        
        collection_title = self.request.POST.get('title')
        
        # Create or get the works
        works = []
        all_authors = set()
        
        for work_data in [first_work, second_work]:
            if not work_data['olid']:
                continue
            
            work = Work.objects.filter(olid=work_data['olid']).first()
            if not work:
                logger.info("Creating new work: %s", work_data)
                work = Work.objects.create(
                    olid=work_data['olid'],
                    title=work_data['title'],
                    search_name=work_data['title'].lower(),
                    type='NOVEL'
                )
                
                # Add authors
                for olid, name in zip(work_data['author_olids'], work_data['author_names']):
                    if olid:
                        author = Author.objects.get_or_fetch(olid)
                        if author:
                            work.authors.add(author)
                            all_authors.add(author)
            else:
                logger.info("Work already exists: %s", work)
                all_authors.update(work.authors.all())
            
            works.append(work)
        
        # Create the collection
        collection = Work.objects.create(
            title=collection_title,
            search_name=collection_title.lower(),
            type='COLLECTION'
        )
        
        # Add authors and component works
        for author in all_authors:
            collection.authors.add(author)
        
        for work in works:
            collection.component_works.add(work)
        
        # Create edition and copy
        edition = Edition.objects.create(
            work=collection,
            publisher=self.request.POST.get('publisher', 'Various'),
            format="PAPERBACK"
        )
        
        # Handle shelving if requested
        copy_data = {
            'edition': edition,
            'condition': "GOOD"
        }
        
        action = self.request.POST.get('action', 'Confirm Without Shelving')
        if action == 'Confirm and Shelve':
            shelf_id = self.request.POST.get('shelf')
            if shelf_id:
                shelf = Shelf.objects.get(id=shelf_id)
                copy_data.update({
                    'shelf': shelf,
                    'location': shelf.bookcase.get_location(),
                    'room': shelf.bookcase.room,
                    'bookcase': shelf.bookcase
                })
        
        Copy.objects.create(**copy_data)
        
        # Create appropriate message
        if action == 'Confirm and Shelve' and 'shelf' in copy_data:
            location_path = (f"{copy_data['location'].name} > {copy_data['room'].name} > "
                            f"{copy_data['bookcase'].name} > Shelf {copy_data['shelf'].position}")
            message = f"new_copy_shelved&title={urllib.parse.quote(collection_title)}&location={urllib.parse.quote(location_path)}"
        else:
            message = f"new_work&title={urllib.parse.quote(collection_title)}"
            
        return HttpResponseRedirect(f'/author/?message={message}') 
