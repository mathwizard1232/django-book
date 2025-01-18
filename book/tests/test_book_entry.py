import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from book.models.author import Author
from book.models.work import Work
from book.tests.pages.author_page import AuthorPage
from book.tests.pages.book_page import BookPage
from book.tests.pages.isbn_page import ISBNPage

@pytest.mark.django_db
class TestBasicBookEntry:
    def test_complete_book_entry_flow(self, browser, requests_mock):
        """Test the complete book entry flow from author search through shelving."""
        
        # Create test author in database
        author = Author.objects.create(
            primary_name="Test Author",
            search_name="test author",
            olid="OL123A"
        )

        # Mock OpenLibrary API responses
        mock_work_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'Test Book',
                'author_name': ['Test Author'],
                'author_key': ['OL123A'],
                'first_publish_year': 2023
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?title=Test+Book&author=OL123A',
            json=mock_work_response
        )

        # Mock OpenLibrary API responses with original title
        mock_work_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'Original Test Book',
                'author_name': ['Test Author'],
                'author_key': ['OL123A'],
                'first_publish_year': 2023
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?title=Original+Test+Book&author=OL123A',
            json=mock_work_response
        )

        # Mock the search that happens during title modification
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL123A&title=Modified+Test+Book&limit=2',
            json=mock_work_response
        )

        # Mock the initial title search
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL123A&title=Original+Test+Book&limit=2',
            json=mock_work_response
        )

        # Start author search and selection
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Test")
        author_page.select_local_author("Test Author")

        # Debug - print current URL
        print(f"Current URL after author selection: {browser.current_url}")

        # Handle title entry
        book_page = BookPage(browser)
        book_page.enter_title("Test Book")
        book_page.confirm_title()

        # Verify book was created
        work = Work.objects.filter(title="Test Book").first()
        assert work is not None
        assert work.authors.first() == author

        # Verify success message
        assert 'added new work' in book_page.get_success_message().lower()
        assert 'test book' in book_page.get_success_message().lower()

    def test_modified_title_book_entry(self, browser, requests_mock):
        """Test that modifying a title during confirmation saves the modified title."""
        
        # Create test author in database
        author = Author.objects.create(
            primary_name="Test Author",
            search_name="test author",
            olid="OL123A"
        )

        # Mock OpenLibrary API responses with original title
        mock_work_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'Original Test Book',
                'author_name': ['Test Author'],
                'author_key': ['OL123A'],
                'first_publish_year': 2023
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?title=Original+Test+Book&author=OL123A',
            json=mock_work_response
        )

        # Mock the search that happens during title modification
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL123A&title=Modified+Test+Book&limit=2',
            json=mock_work_response
        )

        # Start author search and selection
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Test")
        author_page.select_local_author("Test Author")

        # Handle title entry
        book_page = BookPage(browser)
        book_page.enter_title("Original Test Book")
        
        # Modify the title on confirmation page
        modified_title = "Modified Test Book"
        book_page.modify_title_on_confirm(modified_title)
        book_page.confirm_title()

        # Verify book was created with modified title
        work = Work.objects.filter(title="Modified Test Book").first()
        assert work is not None
        assert work.title == "Modified Test Book"
        assert work.authors.first() == author
        assert work.olid == "OL123W"  # Original OpenLibrary ID should be preserved

        # Verify success message
        assert 'added new work' in book_page.get_success_message().lower()
        assert 'modified test book' in book_page.get_success_message().lower()

@pytest.mark.django_db
class TestISBNEntry:
    def test_basic_isbn_entry(self, browser, requests_mock):
        """Test entering a book via ISBN lookup."""
        
        # Mock OpenLibrary ISBN search response
        mock_search_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'Test Book',
                'author_name': ['Test Author'],
                'author_key': ['OL123A'],
                'first_publish_year': 2023,
                'publisher': ['Signet Classics']
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?isbn=0451528557',
            json=mock_search_response
        )
        
        # Create test author in database
        author = Author.objects.create(
            primary_name="Test Author",
            search_name="test author",
            olid="OL123A"
        )
        
        # Start ISBN entry
        isbn_page = ISBNPage(browser)
        isbn_page.navigate()
        isbn_page.enter_isbn("0451528557")
        isbn_page.confirm_isbn()
        
        # Verify book was created
        work = Work.objects.filter(title="Test Book").first()
        assert work is not None
        assert work.authors.first() == author
        
        # Verify success message
        assert 'added new work' in isbn_page.get_success_message().lower()
        assert 'test book' in isbn_page.get_success_message().lower()