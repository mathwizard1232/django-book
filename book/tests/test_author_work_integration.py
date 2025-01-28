import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.sessions.backends.db import SessionStore
from book.models import Author, Work
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

@pytest.mark.django_db(transaction=True)
class TestAuthorWorkIntegration:
    """
    IMPORTANT: These tests should NEVER rely on session state!
    All required data must be passed explicitly in each request.
    
    If you find tests expecting data to persist between requests via session,
    they should be updated to pass all necessary data with each request.
    """
    
    def setup_method(self):
        self.client = Client()

    def test_author_work_connection_from_get_parameters(self):
        """Test that author data is properly maintained when passed explicitly in requests."""
        
        # Create test author with alternate name
        self.author = Author.objects.create(
            primary_name="Test Author",
            search_name="test author",
            olid="OL123A",
            alternate_names=["Different Name"]  # Add alternate name
        )

        # Mock the OpenLibrary search response with different author name
        with patch('book.views.book_views.CachedOpenLibrary') as mock_ol:
            mock_ol_instance = MagicMock()
            mock_ol.return_value = mock_ol_instance
            mock_ol_instance.Work.search.return_value = [{
                'key': '/works/OL123W',
                'title': 'Test Book',
                'author_name': ['Different Name'],  # Return alternate name instead
                'author_key': ['OL123A']
            }]

            # Step 1: Initial GET request with author info in parameters
            response = self.client.get(
                reverse('get_title'),
                {
                    'author_olid': self.author.olid,
                    'author_name': self.author.primary_name,
                    'title': 'Test Book'
                }
            )
            assert response.status_code == 200

            # Step 2: Submit the title search with author data
            response = self.client.post(
                reverse('get_title'),
                {
                    'title': 'Test Book',
                    'author_olid': self.author.olid,
                    'author_name': self.author.primary_name,
                    'author_role': 'AUTHOR'
                }
            )
            assert response.status_code == 302  # Should redirect to confirm page

            # Step 3: Confirm the work creation with the different name from OpenLibrary
            response = self.client.post(
                reverse('confirm_book'),
                {
                    'title': 'Test Book',
                    'work_olid': 'OL123W',
                    'entry_type': 'SINGLE',
                    'author_names': ['Different Name'],  # Use name from OpenLibrary response
                    'author_olids': ['OL123A'],
                    'author_roles': '{"Different Name":"AUTHOR"}'
                }
            )
            assert response.status_code == 302  # Should redirect to success page

            # Verify work was created with correct author despite name mismatch
            work = Work.objects.get(olid='OL123W')
            assert work.title == 'Test Book'
            assert work.authors.count() == 1
            assert work.authors.first() == self.author

    def test_work_creation_with_complete_form_data(self):
        """Test work creation with complete author info in form data"""
        # Create test author
        author = Author.objects.create(
            primary_name="Test Author",
            search_name="test author",
            olid="OL123A"
        )

        # Verify session starts empty
        assert 'selected_author_olid' not in self.client.session
        assert 'selected_author_name' not in self.client.session

        # Submit work creation with complete author info
        response = self.client.post(
            reverse('confirm_book'),
            {
                'title': 'Test Book',
                'work_olid': 'OL123W',
                'author_names': author.primary_name,
                'author_olids': author.olid,
                'author_roles': f'{{"Test Author":"AUTHOR"}}',
                'entry_type': 'SINGLE'
            }
        )
        assert response.status_code == 302

        # Verify work was created with correct author
        work = Work.objects.get(olid='OL123W')
        assert work.title == 'Test Book'
        assert work.authors.count() == 1
        assert work.authors.first() == author

    def test_work_creation_with_different_name(self):
        """Test work creation when form has different name but same OLID"""
        # Create test author
        author = Author.objects.create(
            primary_name="Test Author",
            search_name="test author",
            olid="OL123A"
        )

        # Verify session starts empty
        assert 'selected_author_olid' not in self.client.session
        assert 'selected_author_name' not in self.client.session

        # Submit work creation with different name but complete OLID
        response = self.client.post(
            reverse('confirm_book'),
            {
                'title': 'Test Book',
                'work_olid': 'OL123W',
                'author_names': 'Different Name',
                'author_olids': author.olid,
                'author_roles': '{"Different Name":"AUTHOR"}',
                'entry_type': 'SINGLE',
                'selected_author_olid': author.olid,
                'selected_author_name': author.primary_name
            }
        )
        assert response.status_code == 302

        # Verify work was created with correct author
        work = Work.objects.get(olid='OL123W')
        assert work.title == 'Test Book'
        assert work.authors.count() == 1
        assert work.authors.first() == author

    def test_author_work_connection_with_openlibrary_alternate_name(self):
        """Test that author connection is maintained when OpenLibrary returns an alternate name."""
        
        # Create test author WITHOUT alternate name
        self.author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL123A"
            # No alternate_names set
        )

        # Mock the OpenLibrary work response
        mock_work_response = {
            'key': '/works/OL123W',
            'title': 'Test Book',
            'authors': [{'key': f'/authors/{self.author.olid}'}],  # Use the test author's OLID
            'author_name': ['Frederick Faust'],
            'author_alternative_name': [
                'Brand, Max',
                'Max Brand (pseud.)',
                'Frederick Faust',
                'George Owen Baxter'
            ]
        }
        
        # Add the mock for the work lookup
        with patch('book.views.book_views.CachedOpenLibrary') as mock_ol:
            mock_ol.return_value.Work.get.return_value = SimpleNamespace(**mock_work_response)
            
            # Step 3: Confirm the work creation
            response = self.client.post(
                reverse('confirm_book'),
                {
                    'title': 'Test Book',
                    'work_olid': 'OL123W',
                    'entry_type': 'SINGLE',
                    'author_names': ['Frederick Faust'],
                    'author_olids': [],
                    'author_roles': '{"Frederick Faust":"AUTHOR"}'
                }
            )
            
            assert response.status_code == 302  # Should redirect to success page

            # Verify work was created with correct author
            work = Work.objects.get(olid='OL123W')
            assert work.title == 'Test Book'
            assert work.authors.count() == 1
            assert work.authors.first() == self.author

    def test_author_alternate_olids_from_work_lookup(self):
        """Test that author alternate OLIDs are captured during the full book entry flow."""
        
        # Create test author with just primary name/OLID
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10356294A"
            # No alternate_olids yet
        )

        # Mock OpenLibrary API responses
        with patch('book.views.book_views.CachedOpenLibrary') as mock_ol:
            mock_ol_instance = MagicMock()
            mock_ol.return_value = mock_ol_instance

            # First search by OLID fails (triggers fallback)
            mock_ol_instance.Work.search.side_effect = [
                # First search by OLID returns no results
                [],
                # Second search by name succeeds
                [{
                    'key': '/works/OL123W',
                    'title': 'The Mustang Herder',
                    'author_name': ['Max Brand'],
                    'author_key': ['OL10356294A'],
                    'first_publish_year': 1923,
                    'publisher': ['G.P. Putnam\'s Sons']
                }]
            ]

            # Mock the work lookup that happens during confirmation
            mock_ol_instance.Work.get.return_value = SimpleNamespace(**{
                'key': '/works/OL123W',
                'title': 'The Mustang Herder',
                'authors': [{'key': '/authors/OL10356294A'}],
                'author_name': ['Frederick Faust'],
                'author_alternative_name': [
                    'Brand, Max',
                    'Max Brand (pseud.)',
                    'Frederick Faust',
                    'George Owen Baxter'
                ],
                'alternate_authors': [{'key': '/authors/OL2748402A'}]
            })

            # Step 1: Title search with author info
            response = self.client.post(
                reverse('get_title'),
                {
                    'title': 'The Mustang Herder',
                    'author_olid': author.olid,
                    'author_name': author.primary_name,
                    'author_role': 'AUTHOR'
                }
            )
            assert response.status_code == 302  # Should redirect to confirm page

            # Step 2: Confirm the work creation
            response = self.client.post(
                reverse('confirm_book'),
                {
                    'title': 'The Mustang Herder',
                    'work_olid': 'OL123W',
                    'author_names': author.primary_name,
                    'author_olids': author.olid,
                    'author_roles': f'{{"{author.primary_name}":"AUTHOR"}}',
                    'entry_type': 'SINGLE',
                    'action': 'Confirm Without Shelving'
                }
            )
            assert response.status_code == 302  # Should redirect to success page

            # Verify work was created with proper author
            work = Work.objects.get(olid='OL123W')
            assert work is not None
            assert work.authors.first() == author
            
            # Verify author was updated with alternate info
            author.refresh_from_db()
            assert "Frederick Faust" in author.alternate_names
            assert "Brand, Max" in author.alternate_names
            assert "Max Brand (pseud.)" in author.alternate_names
            assert "George Owen Baxter" in author.alternate_names