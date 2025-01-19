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
        book_page.submit_title_form()
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
        book_page.submit_title_form()
        
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

@pytest.mark.django_db
class TestCollectionBookEntry:
    def test_add_double_book(self, browser, requests_mock):
        """Test adding a book that contains multiple works (like a Belmont Double)."""
        
        # Create test authors in database
        carter = Author.objects.create(
            primary_name="Lin Carter",
            search_name="lin carter",
            olid="OL123A"
        )
        neville = Author.objects.create(
            primary_name="Kris Neville",
            search_name="kris neville",
            olid="OL456A"
        )

        # Mock OpenLibrary API responses for both works
        flame_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'The Flame of Iridar',
                'author_name': ['Lin Carter'],
                'author_key': ['OL123A'],
                'first_publish_year': 1967
            }]
        }
        peril_response = {
            'docs': [{
                'key': '/works/OL456W',
                'title': 'Peril of the Starmen',
                'author_name': ['Kris Neville'],
                'author_key': ['OL456A'],
                'first_publish_year': 1967
            }]
        }
        
        # Mock the API calls
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL123A&title=The+Flame+of+Iridar&limit=2',
            json=flame_response
        )
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL456A&title=Peril+of+the+Starmen&limit=2',
            json=peril_response
        )

        # Start with first work's author
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Lin Carter")
        author_page.select_local_author("Lin Carter")

        # Enter first work's title
        book_page = BookPage(browser)
        book_page.enter_title("The Flame of Iridar")
        book_page.submit_title_form()
        book_page.mark_as_collection()  # This should redirect to author selection for second work
        
        # Select second work's author
        author_page.search_author("Kris Neville")
        author_page.select_local_author("Kris Neville")
        
        # Enter second work's title
        book_page.enter_title("Peril of the Starmen")
        book_page.submit_title_form()
        
        # Now we should be on the collection confirmation page
        # Verify the suggested collection title and confirm
        book_page.verify_collection_title("The Flame of Iridar and Peril of the Starmen")
        book_page.confirm_collection()

        # Verify works were created correctly
        flame = Work.objects.filter(title="The Flame of Iridar").first()
        peril = Work.objects.filter(title="Peril of the Starmen").first()
        collection = Work.objects.filter(type="COLLECTION").first()

        assert flame is not None
        assert peril is not None
        assert collection is not None
        
        # Verify authors
        assert flame.authors.first() == carter
        assert peril.authors.first() == neville
        
        # Verify collection structure
        assert flame in collection.component_works.all()
        assert peril in collection.component_works.all()
        assert collection.title == "The Flame of Iridar and Peril of the Starmen"

        # Verify success message
        # Right now it's 'added new work "the flame of iridar and peril of the starmen" to your library\n×'
        # We don't need to check for the exact message, just that it's a success message
        # Later we may have a more specific message for collections
        assert 'added new work' in book_page.get_success_message().lower()