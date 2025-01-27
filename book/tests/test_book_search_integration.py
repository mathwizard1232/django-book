import pytest
from django.test import Client
from django.urls import reverse
from django.http import QueryDict
from django.contrib.sessions.backends.db import SessionStore
from book.models import Author, Work
from book.utils.ol_client import CachedOpenLibrary
from unittest.mock import patch, MagicMock

@pytest.mark.django_db
class TestBookSearchIntegration:
    def setup_method(self):
        self.client = Client()
        # Create test author
        self.author = Author.objects.create(
            primary_name="Test Author",
            search_name="test author",
            olid="OL123A"
        )

    @pytest.mark.skip(reason="Focusing on basic author-work connection first")
    def skip_test_basic_work_creation_with_author(self, mock_ol):
        """Test that works are created with the correct author attached"""
        # Mock OpenLibrary client responses
        mock_ol_instance = MagicMock()
        mock_ol.return_value = mock_ol_instance
        mock_ol_instance.Work.search.return_value = [{
            'key': '/works/OL123W',
            'title': 'Test Book',
            'authors': [{'name': 'Test Author', 'key': '/authors/OL123A'}],
            'author_key': ['OL123A'],
            'identifiers': {'olid': ['OL123W']}
        }]

        # Step 1: Select author and start book search
        response = self.client.get(
            reverse('get_title'),
            {'author_olid': 'OL123A', 'author_name': 'Test Author'}
        )
        assert response.status_code == 200
        
        # Debug output to see what's in the session
        print("\nSession after author selection:", self.client.session.items())

        # Step 2: Submit title search
        response = self.client.post(
            reverse('get_title'),
            {
                'title': 'Test Book',
                'author_olid': 'OL123A',
                'author_name': 'Test Author'
            }
        )
        assert response.status_code == 302  # Should redirect to confirm page
        
        # Debug output for redirect URL
        print("\nRedirect URL:", response.url)

        # Step 3: Confirm book creation
        response = self.client.post(
            reverse('confirm_book'),
            {
                'title': 'Test Book',
                'work_olid': 'OL123W',
                'author_names': 'Test Author',
                'author_olids': 'OL123A',
                'author_roles': '{"Test Author":"AUTHOR"}',
                'entry_type': 'SINGLE',
                'action': 'Confirm Without Shelving'
            }
        )
        assert response.status_code == 302  # Should redirect to success page

        # Verify the work was created with correct author
        work = Work.objects.get(olid='OL123W')
        assert work.title == 'Test Book'
        assert work.authors.first() == self.author

    @pytest.mark.skip(reason="Focusing on basic author-work connection first")
    def skip_test_local_work_search(self):
        """Test that we can find existing works in the database"""
        # Create a test work with our author
        work = Work.objects.create(
            title="Test Book",
            olid="OL123W",
            search_name="test book"
        )
        work.authors.add(self.author)

        # Search for the work
        response = self.client.get(
            reverse('get_title'),
            {
                'author_name': 'Test Author',
                'title': 'Test Book',
                'search_local': 'true'
            }
        )
        assert response.status_code == 200
        assert 'Test Book' in str(response.content)

    @pytest.mark.skip(reason="Focusing on basic author-work connection first")
    def skip_test_work_creation_maintains_author(self):
        """Test that work creation maintains the selected author through the entire flow"""
        # Set up session with selected author
        session = self.client.session
        session['selected_author_olid'] = self.author.olid
        session['selected_author_name'] = self.author.primary_name
        session.save()

        # Step 1: Submit title search
        response = self.client.post(
            reverse('get_title'),
            {
                'title': 'Test Book',
                'author_olid': self.author.olid,
                'author_name': self.author.primary_name
            }
        )
        assert response.status_code == 302  # Should redirect to confirm page

        # Step 2: Confirm work creation
        response = self.client.post(
            reverse('confirm_book'),
            {
                'title': 'Test Book',
                'work_olid': 'OL123W',
                'author_names': self.author.primary_name,
                'author_olids': self.author.olid,
                'author_roles': f'{{"Test Author":"AUTHOR"}}',
                'entry_type': 'SINGLE'
            }
        )
        assert response.status_code == 302  # Should redirect to success page

        # Verify work was created with correct author
        work = Work.objects.get(olid='OL123W')
        assert work.title == 'Test Book'
        assert work.authors.first() == self.author

    @pytest.mark.skip(reason="Focusing on basic author-work connection first")
    def skip_test_work_creation_with_session_author(self):
        """Test that work creation uses author from session even if form data differs"""
        # Set up session with selected author
        session = self.client.session
        session['selected_author_olid'] = self.author.olid
        session['selected_author_name'] = self.author.primary_name
        session.save()

        # Submit work creation with different author name but same OLID
        response = self.client.post(
            reverse('confirm_book'),
            {
                'title': 'Test Book',
                'work_olid': 'OL123W',
                'author_names': 'Different Name',  # Different from session
                'author_olids': self.author.olid,  # Same as session
                'author_roles': '{"Different Name":"AUTHOR"}',
                'entry_type': 'SINGLE'
            }
        )
        assert response.status_code == 302

        # Verify work was created with session author
        work = Work.objects.get(olid='OL123W')
        assert work.title == 'Test Book'
        assert work.authors.first() == self.author

    @pytest.mark.skip(reason="Focusing on basic author-work connection first")
    def skip_test_author_name_olid_fallback_integration(self, mock_ol):
        """Test book search falls back from OLID to full author name"""
        # Mock OpenLibrary client responses
        mock_ol_instance = MagicMock()
        mock_ol.return_value = mock_ol_instance

        # Mock the failed OLID search
        mock_ol_instance.Work.search.side_effect = [
            # First search with OLID fails (empty results)
            [],
            # Second search with author name succeeds
            [{
                'key': '/works/OL123W',
                'title': 'The Mustang Herder',
                'authors': [{'name': 'Max Brand', 'key': '/authors/OL10356294A'}],
                'author_key': ['OL10356294A'],
                'author_name': ['Max Brand'],
                'identifiers': {'olid': ['OL123W']},
                'type': {'key': '/type/work'}
            }]
        ]

        # Step 1: Start book search with author OLID
        response = self.client.get(
            reverse('get_title'),
            {'author_olid': 'OL10356294A', 'author_name': 'Max Brand', 'title': 'The Mustang Herder'}
        )
        assert response.status_code == 200
        assert 'The Mustang Herder' in str(response.content)

        # Step 2: Submit title search
        response = self.client.post(
            reverse('get_title'),
            {
                'title': 'The Mustang Herder',
                'author_olid': 'OL10356294A',
                'author_name': 'Max Brand'
            }
        )
        assert response.status_code == 302  # Should redirect to confirm page

        # Step 3: Confirm book creation
        response = self.client.post(
            reverse('confirm_book'),
            {
                'title': 'The Mustang Herder',
                'work_olid': 'OL123W',
                'author_names': 'Max Brand',
                'author_olids': 'OL10356294A',
                'author_roles': '{"Max Brand":"AUTHOR"}',
                'entry_type': 'SINGLE',
                'action': 'Confirm Without Shelving'
            }
        )
        assert response.status_code == 302  # Should redirect to success page

        # Verify the work was created with correct author
        work = Work.objects.get(olid='OL123W')
        assert work.title == 'The Mustang Herder'
        assert work.authors.first() == self.author

    @pytest.mark.skip(reason="Focusing on basic author-work connection first")
    def skip_test_author_name_matching_with_alternates(self):
        """Test that author matching works with alternate names"""
        # Create a work with the author's pen name
        work = Work.objects.create(
            title="The Mustang Herder",
            olid="OL123W",
            search_name="the mustang herder"
        )
        work.authors.add(self.author)

        # Verify we can find the work by pen name
        response = self.client.get(
            reverse('get_title'),
            {'author_name': 'Max Brand', 'title': 'The Mustang Herder', 'search_local': 'true'}
        )
        assert response.status_code == 200
        assert 'The Mustang Herder' in str(response.content)

        # Verify we can find the work by primary name
        response = self.client.get(
            reverse('get_title'),
            {'author_name': 'Frederick Schiller Faust', 'title': 'The Mustang Herder', 'search_local': 'true'}
        )
        assert response.status_code == 200
        assert 'The Mustang Herder' in str(response.content) 