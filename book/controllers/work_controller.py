from typing import Dict, List, Optional, Tuple
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponseBadRequest
import logging
import urllib.parse
import json

from ..models import Work, Author, Edition, Copy, Shelf, Location
from ..utils.ol_client import CachedOpenLibrary

logger = logging.getLogger(__name__)

class WorkController:
    def __init__(self, request: HttpRequest):
        self.request = request
        self.ol_client = CachedOpenLibrary()
        
    def handle_book_confirmation(self) -> HttpResponse:
        """Process the confirmed book selection and create local records"""
        # Log request context
        self._log_request_context()
        
        # Early returns
        if self.request.POST.get('collection_first_work'):
            return self._handle_collection_confirmation()
            
        if not self.request.POST.get('work_olid'):
            return HttpResponseBadRequest('work_olid required')
            
        # Get basic work data
        work_data = self._get_work_data()
        if not work_data:
            return HttpResponseBadRequest('Could not fetch work data')
            
        # Check for existing work with copies
        existing_work = self._check_existing_work()
        if existing_work:
            return existing_work
            
        # Process authors
        authors, editors = self._process_authors(work_data)
        
        # Create or get work
        work = self._create_or_get_work(authors, editors)
        
        # Handle editions and copies
        message = self._handle_editions_and_copies(work)
        
        return HttpResponseRedirect(f'/author/?message={message}')
        
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
        
        # Parse author roles
        try:
            author_roles = json.loads(self.request.POST.get('author_roles', '{}'))
        except json.JSONDecodeError:
            logger.warning("Could not parse author_roles JSON")
            author_roles = {}
            
        # Check for selected author from form only
        selected_author = None
        selected_olid = self.request.POST.get('selected_author_olid')
        
        if selected_olid:
            selected_author = Author.objects.filter(olid=selected_olid).first()
            logger.info("Found selected author: %s", selected_author)
            
        # Process each author
        for olid in author_olids:
            author = self._get_or_create_author(
                olid=olid,
                selected_author=selected_author,
                author_names=author_names,
                author_roles=author_roles,
                work_data=work_data
            )
            
            if author:
                # Update alternate names from work data if available
                if hasattr(work_data, 'author_alternative_name'):
                    if not author.alternate_names:
                        author.alternate_names = []
                    for alt_name in work_data.author_alternative_name:
                        if alt_name not in author.alternate_names:
                            author.alternate_names.append(alt_name)
                    author.save()
                
                if author_roles.get(author.primary_name, 'AUTHOR') == 'AUTHOR':
                    authors.append(author)
                else:
                    editors.append(author)
                    
        return authors, editors
        
    def _get_or_create_author(self, olid: str, selected_author: Optional[Author], 
                             author_names: List[str], author_roles: Dict[str, str],
                             work_data: Dict) -> Optional[Author]:
        """Get existing author or create new one with proper name formatting"""
        # If we have a selected author, update and return it
        if selected_author:
            try:
                author_details = self.ol_client.Author.get(olid)
                if author_details:
                    self._update_author_details(selected_author, author_details)
                return selected_author
            except Exception as e:
                logger.warning(f"Error getting author details: {e}")
                return selected_author
                
        # Try to find existing author
        author = Author.objects.filter(olid=olid).first()
        if author:
            return author
            
        # Try to match by alternate names in work data
        if work_data and hasattr(work_data, 'author_alternative_name'):
            alt_names = [name.lower() for name in work_data.author_alternative_name]
            for local_author in Author.objects.all():
                if local_author.search_name in alt_names:
                    logger.info("Found matching local author by alternate name: %s", local_author)
                    return local_author
                    
        # Create new author if needed
        for name in author_names:
            if author_roles.get(name) == "AUTHOR":
                try:
                    author_details = self.ol_client.Author.get(olid)
                    if author_details:
                        return self._create_author_with_details(name, olid, author_details)
                except Exception as e:
                    logger.warning(f"Error getting author details: {e}")
                    # Fall back to basic author creation
                    return Author.objects.create(
                        primary_name=name,
                        search_name=name.lower(),
                        olid=olid
                    )
                    
        return None
        
    def _update_author_details(self, author: Author, author_details: Dict) -> None:
        """Update author with details from OpenLibrary"""
        alternate_names = author_details.get('alternate_names', [])
        real_name = author_details.get('personal_name') or author_details.get('name')
        
        if real_name:
            formatted_name = self._format_pen_name(
                real_name=real_name,
                pen_name=author.search_name.title(),
                alternate_names=alternate_names
            )
            author.primary_name = formatted_name
            author.alternate_names = alternate_names
            author.save()
            
    def _create_author_with_details(self, name: str, olid: str, 
                                  author_details: Dict) -> Author:
        """Create new author with OpenLibrary details"""
        alternate_names = author_details.get('alternate_names', [])
        real_name = author_details.get('personal_name') or author_details.get('name')
        
        if real_name:
            formatted_name = self._format_pen_name(
                real_name=real_name,
                pen_name=name,
                alternate_names=alternate_names
            )
        else:
            formatted_name = name
            
        return Author.objects.create(
            primary_name=formatted_name,
            search_name=name.lower(),
            olid=olid,
            alternate_names=alternate_names
        )
        
    def _format_pen_name(self, real_name: str, pen_name: str, 
                        alternate_names: List[str]) -> str:
        """Format author name to include pen name if appropriate"""
        # Split names into components and just use first and last
        name_parts = real_name.split()
        real_first = name_parts[0]
        real_last = name_parts[-1]
        
        # Check if components of real name appear in alternate names
        for alt_name in alternate_names:
            if real_first.lower() in alt_name.lower() and real_last.lower() in alt_name.lower():
                return f"{real_first} '{pen_name}' {real_last}"
                
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
        """Handle the confirmation of a second work to create a collection"""
        # Get both works' details from POST data
        first_work = {
            'title': self.request.POST.get('first_work_title'),
            'work_olid': self.request.POST.get('first_work_olid'),
            'author_names': self.request.POST.get('first_work_author_names'),
            'author_olids': self.request.POST.get('first_work_author_olids'),
            'publisher': self.request.POST.get('first_work_publisher'),
        }
        
        second_work = {
            'title': self.request.POST.get('second_work_title'),
            'work_olid': self.request.POST.get('second_work_olid'),
            'author_names': self.request.POST.get('second_work_author_names'),
            'author_olids': self.request.POST.get('second_work_author_olids'),
            'publisher': self.request.POST.get('publisher'),
        }
        
        # Create the collection work
        collection_title = self.request.POST.get('title')
        collection = Work.objects.create(
            title=collection_title,
            search_name=collection_title,
            type='COLLECTION'
        )
        
        # Create and link the component works
        works_to_create = [first_work, second_work]
        contained_works = []
        all_authors = set()
        
        for work_data in works_to_create:
            logger.info("Processing work data: %s", work_data)
            work = Work.objects.filter(olid=work_data['work_olid']).first()
            if not work:
                work = Work.objects.create(
                    olid=work_data['work_olid'],
                    title=work_data['title'],
                    search_name=work_data['title'],
                    type='NOVEL'
                )
                
                # Add authors
                if work_data['author_olids']:
                    for olid, name in zip(work_data['author_olids'].split(','), 
                                        work_data['author_names'].split(',')):
                        if olid:
                            author = Author.objects.get_or_fetch(olid)
                            if author:
                                work.authors.add(author)
                                all_authors.add(author)
            else:
                all_authors.update(work.authors.all())
            
            contained_works.append(work)
            
        # Add all collected authors to the collection
        for author in all_authors:
            collection.authors.add(author)
        
        # Link both works to the collection
        for work in contained_works:
            collection.component_works.add(work)
            
        # Create edition and copy
        edition = Edition.objects.create(
            work=collection,
            publisher="Various" if first_work['publisher'] != second_work['publisher'] else first_work['publisher'],
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
        if action == 'Confirm and Shelve' and shelf_id:
            location_path = f"{shelf.bookcase.get_location().name} > {shelf.bookcase.room.name} > {shelf.bookcase.name} > Shelf {shelf.position}"
            message = f"new_copy_shelved&title={urllib.parse.quote(collection_title)}&location={urllib.parse.quote(location_path)}"
        else:
            message = f"new_work&title={urllib.parse.quote(collection_title)}"
            
        return HttpResponseRedirect(f'/author/?message={message}') 
