from django.test import TestCase
from django.db.utils import NotSupportedError
from book.models import Author, Work
from book.views.book_views import _handle_book_confirmation
from django.http import HttpRequest, QueryDict
from django.contrib.sessions.backends.db import SessionStore
from unittest.mock import patch
import requests_mock
import requests

class TestWorkCreation(TestCase):
    def setUp(self):
        # Create a test author
        self.author = Author.objects.create(
            primary_name="Test Author",
            search_name="test author",
            olid="OL123A"
        )

    def test_basic_work_creation(self):
        """Test creating a work with basic fields"""
        work = Work.objects.create(
            title="Test Book",
            search_name="test book",
            olid="OL123W",
            type="NOVEL"
        )
        
        # Verify basic fields
        self.assertEqual(work.title, "Test Book")
        self.assertEqual(work.search_name, "test book")
        self.assertEqual(work.olid, "OL123W")
        self.assertEqual(work.type, "NOVEL")
        
    def test_work_with_single_author(self):
        """Test creating a work and associating an author"""
        work = Work.objects.create(
            title="Test Book",
            search_name="test book",
            olid="OL123W",
            type="NOVEL"
        )
        
        # Add author
        work.authors.add(self.author)
        
        # Verify author association
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), self.author)
        
    def test_work_with_author_role(self):
        """Test creating a work with author role handling"""
        work = Work.objects.create(
            title="Test Book",
            search_name="test book",
            olid="OL123W",
            type="NOVEL"
        )
        
        # Test author role mapping
        author_roles = {self.author.primary_name: "AUTHOR"}
        if author_roles.get(self.author.primary_name) == "AUTHOR":
            work.authors.add(self.author)
        else:
            work.editors.add(self.author)
            
        # Verify correct role assignment
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.editors.count(), 0)
        self.assertEqual(work.authors.first(), self.author)
        
    def test_work_with_author_olid(self):
        """Test creating a work and associating an author by OLID"""
        work = Work.objects.create(
            title="Test Book",
            search_name="test book",
            olid="OL123W",
            type="NOVEL"
        )
        
        # Test author association by OLID
        author_olids = [self.author.olid]
        author_roles = {self.author.primary_name: "AUTHOR"}
        
        # Add author using the same logic as the view
        for olid in author_olids:
            try:
                author = Author.objects.get(olid=olid)
                if author_roles.get(author.primary_name) == "AUTHOR":
                    work.authors.add(author)
                else:
                    work.editors.add(author)
            except Author.DoesNotExist:
                continue
                
        # Verify author association
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), self.author)
        
    def test_work_with_author_name_fallback(self):
        """Test creating a work and associating an author by name when OLID fails"""
        work = Work.objects.create(
            title="Test Book",
            search_name="test book",
            olid="OL123W",
            type="NOVEL"
        )
        
        # Test author association with name fallback
        author_names = [self.author.primary_name]
        author_roles = {self.author.primary_name: "AUTHOR"}
        
        # Add author using the same logic as the view
        for name in author_names:
            try:
                author = Author.objects.get(primary_name=name)
                if author_roles.get(name) == "AUTHOR":
                    work.authors.add(author)
                else:
                    work.editors.add(author)
            except Author.DoesNotExist:
                continue
                
        # Verify author association
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), self.author)
        
    def test_work_with_alternate_name_fallback(self):
        """Test creating a work and associating an author through alternate names"""
        # Add alternate name to test author
        self.author.alternate_names = ["Frederick Faust"]
        self.author.save()
        
        work = Work.objects.create(
            title="Test Book",
            search_name="test book",
            olid="OL123W",
            type="NOVEL"
        )
        
        # Test author association with alternate name
        author_names = ["Frederick Faust"]  # Using alternate name
        author_roles = {"Frederick Faust": "AUTHOR"}
        
        # Add author using expanded lookup logic
        for name in author_names:
            try:
                # Try primary name first
                author = Author.objects.get(primary_name=name)
            except Author.DoesNotExist:
                # Try alternate names
                # Get all authors and filter in Python for SQLite compatibility
                for potential_author in Author.objects.all():
                    if name in potential_author.alternate_names:
                        author = potential_author
                        break
                else:  # No match found
                    continue
                    
            if author_roles.get(name) == "AUTHOR":
                work.authors.add(author)
            else:
                work.editors.add(author)
                
        # Verify author association
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), self.author)
        
    def test_work_with_mismatched_author_names(self):
        """Test work creation when OpenLibrary returns different author name than search"""
        # Create author with both names
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10356294A",
            alternate_names=["Frederick Faust"]
        )
        
        work = Work.objects.create(
            title="Test Book",
            search_name="test book",
            olid="OL123W",
            type="NOVEL"
        )
        
        # Simulate the view's scenario where we search with one name
        # but get results with a different name
        search_name = "Max Brand"
        result_name = "Frederick Faust"
        
        author_names = [result_name]  # OpenLibrary returned this name
        author_roles = {result_name: "AUTHOR"}  # Using the returned name in roles
        author_olids = []  # No OLID in this case
        
        # Try to associate author using the same logic as the view
        for name in author_names:
            try:
                # Try primary name first
                author = Author.objects.get(primary_name=name)
                if author_roles.get(name) == "AUTHOR":
                    work.authors.add(author)
                else:
                    work.editors.add(author)
            except Author.DoesNotExist:
                # Try alternate names
                # Get all authors and filter in Python for SQLite compatibility
                for potential_author in Author.objects.all():
                    if name in potential_author.alternate_names:
                        author = potential_author
                        break
                else:  # No match found
                    continue
                    
                if author_roles.get(name) == "AUTHOR":
                    work.authors.add(author)
                else:
                    work.editors.add(author)
                
        # Verify author association
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), author)

    def test_work_creation_with_selected_author(self):
        """Test work creation maintains association with originally selected author"""
        # Create our test author
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10356294A"
        )
        
        # Create work with the data that would come from the form
        work = Work.objects.create(
            title="The Mustang Herder",
            search_name="the mustang herder",
            olid="OL123W",
            type="NOVEL"
        )
        
        # Simulate the view's processing where OpenLibrary returns a different name
        selected_author_olid = "OL10356294A"  # The author we selected
        returned_author_name = "Frederick Faust"  # The name OpenLibrary returns
        
        author_names = [returned_author_name]
        author_roles = {returned_author_name: "AUTHOR"}
        author_olids = [selected_author_olid]  # We should still have this from selection!
        
        # Try to associate author using the same logic as the view
        for name in author_names:
            try:
                # First try by primary name (this will fail)
                author = Author.objects.get(primary_name=name)
            except Author.DoesNotExist:
                # Should fall back to using the OLID we got during selection
                try:
                    author = Author.objects.get(olid=selected_author_olid)
                except Author.DoesNotExist:
                    continue
                
            if author_roles.get(name) == "AUTHOR":
                work.authors.add(author)
            else:
                work.editors.add(author)
            
        # Verify author association
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), author)

    def test_work_creation_preserves_selected_author_olid(self):
        """Test work creation maintains association with originally selected author via OLID"""
        # Create our test author
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10356294A"
        )
        
        # Create work with the data that would come from the form
        work = Work.objects.create(
            title="The Mustang Herder",
            search_name="the mustang herder",
            olid="OL123W",
            type="NOVEL"
        )
        
        # Simulate the view's processing where OpenLibrary returns a different name
        selected_author_olid = "OL10356294A"  # The author we selected
        returned_author_name = "Frederick Faust"  # The name OpenLibrary returns
        
        author_names = [returned_author_name]
        author_roles = {returned_author_name: "AUTHOR"}
        author_olids = [selected_author_olid]  # We should still have this from selection!
        
        # Try to associate author using the same logic as the view
        for name in author_names:
            try:
                # First try by primary name (this will fail)
                author = Author.objects.get(primary_name=name)
            except Author.DoesNotExist:
                # Should fall back to using the OLID we got during selection
                try:
                    author = Author.objects.get(olid=selected_author_olid)
                except Author.DoesNotExist:
                    continue
                
            if author_roles.get(name) == "AUTHOR":
                work.authors.add(author)
            else:
                work.editors.add(author)
            
        # Verify author association
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), author)

    def test_work_creation_maintains_selected_author_when_olid_missing_from_search(self):
        """Test work creation maintains selected author when title search returns no OLID"""
        from django.http import HttpRequest
        from django.contrib.sessions.backends.db import SessionStore
        from book.views.book_views import _handle_book_confirmation
        from book.models import Work
        
        # Create our test author
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10356294A"
        )
        
        # Create a request object with POST data
        request = HttpRequest()
        request.method = 'POST'
        request.POST = {
            'title': 'The Mustang Herder',
            'work_olid': 'OL123W',
            'author_names': 'Frederick Faust',  # Different name from search results
            'author_olids': 'OL10356294A',  # But we have the OLID from selection
            'author_roles': '{"Frederick Faust":"AUTHOR"}',
            'entry_type': 'SINGLE'
        }
        
        # Add session support
        request.session = SessionStore()
        request.session.create()
        
        # Call the view function (which returns a redirect)
        response = _handle_book_confirmation(request)
        
        # Look up the created work
        work = Work.objects.get(olid='OL123W')
        
        # Verify author association
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), author) 

    def test_work_creation_maintains_author_through_search_and_confirmation(self):
        """Test that work creation maintains the selected author through both search and confirmation"""
        from django.http import QueryDict
        from book.views import get_title
        from book.views.book_views import _handle_book_confirmation
        
        # Create our test author first
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10356294A"
        )
        
        # First simulate the title search step
        search_request = HttpRequest()
        search_request.method = 'POST'
        search_request.session = SessionStore()
        search_request.session.create()
        
        # Store the author info in session like the selection would
        search_request.session['selected_author_olid'] = author.olid
        search_request.session['selected_author_name'] = author.primary_name
        
        # This matches what we see in the title search step
        search_request.POST = QueryDict('', mutable=True)
        search_request.POST.update({
            'title': 'The Mustang Herder',
            'author_olid': author.olid,
            'author_name': 'Max Brand'
        })
        
        # Call the title entry function
        search_response = get_title(search_request)
        
        # Now simulate the confirmation step
        confirm_request = HttpRequest()
        confirm_request.method = 'POST'
        confirm_request.session = search_request.session  # Maintain the same session
        
        # This matches what we see in the confirmation step
        confirm_request.POST = QueryDict('', mutable=True)
        confirm_request.POST.update({
            'title': 'The Mustang Herder',
            'work_olid': 'OL123W',
            'author_names': 'Frederick Faust',  # Different name from search
            'author_olids': author.olid,  # Should still have the original OLID
            'author_roles': '{"Frederick Faust":"AUTHOR"}',
            'entry_type': 'SINGLE'
        })
        
        # Call the confirmation function
        confirm_response = _handle_book_confirmation(confirm_request)
        
        # Look up the created work
        work = Work.objects.get(olid='OL123W')
        
        # Verify author association was maintained through both steps
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), author) 

    def test_work_creation_maintains_author_when_found_by_different_name(self):
        """Test work creation maintains author when OpenLibrary search finds them by a different name"""
        from django.http import QueryDict
        from book.views.book_views import _handle_book_confirmation
        
        # Create our test author with alternate names
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10356294A",
            alternate_names=["Frederick Faust", "George Owen Baxter"]
        )
        
        # Create a request object with POST data
        request = HttpRequest()
        request.method = 'POST'
        request.session = SessionStore()
        request.session.create()
        
        # Store the original author selection in session
        request.session['selected_author_olid'] = author.olid
        request.session['selected_author_name'] = author.primary_name
        
        # This simulates what happens when OpenLibrary returns results with a different name
        request.POST = QueryDict('', mutable=True)
        request.POST.update({
            'title': 'The Mustang Herder',
            'work_olid': 'OL123W',
            'author_names': 'Frederick Faust',  # Different name from what we selected
            'author_olids': '',  # OpenLibrary result doesn't include the OLID
            'author_roles': '{"Frederick Faust":"AUTHOR"}',
            'entry_type': 'SINGLE'
        })
        
        # Call the confirmation function
        response = _handle_book_confirmation(request)
        
        # Look up the created work
        work = Work.objects.get(olid='OL123W')
        
        # Verify author association was maintained
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), author) 

    def test_work_creation_preserves_author_through_confirmation(self):
        """Test that work creation preserves author association through the confirmation process"""
        # Create our test author
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10356294A"
        )
        
        # Create a request object with POST data that matches what we see in the failing tests
        request = HttpRequest()
        request.method = 'POST'
        request.session = SessionStore()
        request.session.create()
        
        # Store the author info in session like the selection would
        request.session['selected_author_olid'] = author.olid
        request.session['selected_author_name'] = author.primary_name
        
        # This matches what we see in the failing confirmation step
        request.POST = QueryDict('', mutable=True)
        request.POST.update({
            'title': 'The Mustang Herder',
            'work_olid': 'OL123W',
            'author_names': 'Max Brand',  # Using primary name
            'author_olids': author.olid,
            'author_roles': '{"Max Brand":"AUTHOR"}',
            'entry_type': 'SINGLE'
        })
        
        # Call the confirmation function
        response = _handle_book_confirmation(request)
        
        # Look up the created work
        work = Work.objects.get(olid='OL123W')
        
        # Verify author association was maintained
        self.assertEqual(work.authors.count(), 1)
        self.assertEqual(work.authors.first(), author) 

    def test_work_creation_formats_pen_name(self):
        """Test work creation properly formats pen name when real name is discovered"""
        from django.http import QueryDict
        from book.views.book_views import _handle_book_confirmation
        import requests
        from unittest.mock import patch
        from django.contrib.sessions.backends.db import SessionStore
        
        # Create our test author with just the pen name initially
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10352592A"
        )
        
        # Create a request object with POST data
        request = HttpRequest()
        request.method = 'POST'
        request.session = SessionStore()  # Add empty session
        request.session.create()
        
        # Mock the OpenLibrary work response that reveals the real name
        request.POST = QueryDict('', mutable=True)
        request.POST.update({
            'title': 'The Mustang Herder',
            'work_olid': 'OL14848834W',
            'author_names': 'Frederick Faust',  # Real name
            'author_olids': 'OL2748402A',      # Different OLID
            'author_roles': '{"Frederick Faust":"AUTHOR"}',
            'entry_type': 'SINGLE',
            'selected_author_olid': author.olid,  # Pass through form instead of session
            'selected_author_name': author.primary_name
        })

        # Mock the requests.get call for OpenLibrary author details
        mock_response = {
            'name': 'Frederick Faust',
            'personal_name': 'Frederick Schiller Faust',
            'alternate_names': ['Brand, Max', 'George Owen Baxter'],
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944'
        }
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.status_code = 200
            
            # Process the work creation
            response = _handle_book_confirmation(request)
        
        # Verify the author was updated with formatted name
        author.refresh_from_db()
        assert author.primary_name == "Frederick 'Max Brand' Faust"
        assert author.search_name == "max brand"  # Search name should remain unchanged
        assert "Brand, Max" in author.alternate_names
        assert "George Owen Baxter" in author.alternate_names
        
        # Verify the work was created and associated
        work = Work.objects.get(olid="OL14848834W")
        assert work.authors.first() == author 