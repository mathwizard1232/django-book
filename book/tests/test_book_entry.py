import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from book.models.author import Author
from book.models.work import Work
from book.tests.pages.author_page import AuthorPage
from book.tests.pages.book_page import BookPage
from book.tests.pages.isbn_page import ISBNPage
from urllib.parse import parse_qs, urlparse

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

        # Mock OpenLibrary author autocomplete API
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Test&limit=5',
            json=[{
                'name': 'Test Author',
                'key': '/authors/OL123A'
            }]
        )

        # Mock the full author details API
        requests_mock.get(
            'https://openlibrary.org/authors/OL123A.json',
            json={
                'key': '/authors/OL123A',
                'name': 'Test Author',
                'personal_name': 'Test Author',
                'birth_date': '1900',
                'death_date': '1980'
            }
        )

        # Mock work search API
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

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'Test Book',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'},
                'first_publish_date': '2023'
            }
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

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'Test Book',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'},
                'first_publish_date': '2023'
            }
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

        # Mock OpenLibrary API responses - note these return different combined works
        flame_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'The Flame of Iridar and Peril of the Starmen',
                'author_name': ['Lin Carter'],
                'author_key': ['OL123A'],
                'first_publish_year': 1967
            }]
        }
        peril_response = {
            'docs': [{
                'key': '/works/OL456W',
                'title': 'Peril of the Starmen & The Forgotten Planet',
                'author_name': ['Kris Neville'],
                'author_key': ['OL456A'],
                'first_publish_year': 1967
            }]
        }
        
        # Mock the API calls - each search returns its own combined work
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL123A&title=The+Flame+of+Iridar&limit=2',
            json=flame_response
        )
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL456A&title=Peril+of+the+Starmen&limit=2',
            json=peril_response
        )

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'The Flame of Iridar',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'},
                'first_publish_date': '1967'
            }
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
        book_page.modify_title_on_confirm("The Flame of Iridar")
        book_page.mark_as_collection()  # This should redirect to author selection for second work
        
        # Select second work's author
        author_page.search_author("Kris Neville")
        author_page.select_local_author("Kris Neville")
        
        # Enter second work's title
        book_page.enter_title("Peril of the Starmen")
        book_page.submit_title_form()
        
        # Now we should be on the collection confirmation page
        # Fix both the second work's title and the collection title
        book_page.modify_second_work_title("Peril of the Starmen")
        book_page.modify_collection_title("The Flame of Iridar and Peril of the Starmen")
        book_page.confirm_collection()

        # Verify works were created correctly with modified titles
        flame = Work.objects.filter(title="The Flame of Iridar").first()
        peril = Work.objects.filter(title="Peril of the Starmen").first()
        collection = Work.objects.filter(type="COLLECTION").first()

        assert flame is not None
        assert peril is not None
        assert collection is not None
        assert collection.title == "The Flame of Iridar and Peril of the Starmen"  # Verify the collection title
        
        # Verify authors
        assert flame.authors.first() == carter
        assert peril.authors.first() == neville
        
        # Verify collection structure with modified titles
        assert flame in collection.component_works.all()
        assert peril in collection.component_works.all()
        assert collection.title == "The Flame of Iridar and Peril of the Starmen"

        # Verify collection authors
        assert set(collection.authors.all()) == {carter, neville}

        # Verify individual works have correct single authors and modified titles
        assert flame.authors.count() == 1
        assert peril.authors.count() == 1
        assert flame.authors.first() == carter
        assert peril.authors.first() == neville
        assert flame.title == "The Flame of Iridar"  # Verify modified title stuck
        assert peril.title == "Peril of the Starmen"  # Verify modified title stuck

        # Verify success message includes the collection title
        assert 'added new work' in book_page.get_success_message().lower()
        assert 'the flame of iridar and peril of the starmen' in book_page.get_success_message().lower()

    def test_modified_titles_collection_entry(self, browser, requests_mock):
        """Test that modifying individual work titles during collection creation saves correctly."""
        
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

        # Mock OpenLibrary API responses - note these return different combined works
        flame_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'The Flame of Iridar and Peril of the Starmen',
                'author_name': ['Lin Carter'],
                'author_key': ['OL123A'],
                'first_publish_year': 1967
            }]
        }
        peril_response = {
            'docs': [{
                'key': '/works/OL456W',
                'title': 'Peril of the Starmen & The Forgotten Planet',
                'author_name': ['Kris Neville'],
                'author_key': ['OL456A'],
                'first_publish_year': 1967
            }]
        }
        
        # Mock the API calls - each search returns its own combined work
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL123A&title=The+Flame+of+Iridar&limit=2',
            json=flame_response
        )
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL456A&title=Peril+of+the+Starmen&limit=2',
            json=peril_response
        )

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'The Flame of Iridar',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'},
                'first_publish_date': '1967'
            }
        )

        # Start with first work's author and title
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Lin Carter")
        author_page.select_local_author("Lin Carter")

        # Enter first work's title - note we search for just the first title
        book_page = BookPage(browser)
        book_page.enter_title("The Flame of Iridar")
        book_page.submit_title_form()
        book_page.modify_title_on_confirm("The Flame of Iridar")  # Fix the title from combined result
        book_page.mark_as_collection()
        
        # Select second work's author
        author_page.search_author("Kris Neville")
        author_page.select_local_author("Kris Neville")
        
        # Enter second work's title
        book_page.enter_title("Peril of the Starmen")
        book_page.submit_title_form()
        
        # Now we should be on the collection confirmation page
        # Fix both the second work's title and the collection title
        book_page.modify_second_work_title("Peril of the Starmen")
        book_page.modify_collection_title("The Flame of Iridar and Peril of the Starmen")
        book_page.confirm_collection()

        # Verify works were created correctly with modified titles
        flame = Work.objects.filter(title="The Flame of Iridar").first()
        peril = Work.objects.filter(title="Peril of the Starmen").first()
        collection = Work.objects.filter(type="COLLECTION").first()

        assert flame is not None
        assert peril is not None
        assert collection is not None
        
        # Verify authors
        assert flame.authors.first() == carter
        assert peril.authors.first() == neville
        
        # Verify collection structure with modified titles
        assert flame in collection.component_works.all()
        assert peril in collection.component_works.all()
        assert collection.title == "The Flame of Iridar and Peril of the Starmen"

        # Verify collection authors
        assert set(collection.authors.all()) == {carter, neville}

        # Verify individual works have correct single authors and modified titles
        assert flame.authors.count() == 1
        assert peril.authors.count() == 1
        assert flame.authors.first() == carter
        assert peril.authors.first() == neville
        assert flame.title == "The Flame of Iridar"  # Verify modified title stuck
        assert peril.title == "Peril of the Starmen"  # Verify modified title stuck

        # Verify success message includes the collection title
        assert 'added new work' in book_page.get_success_message().lower()
        assert 'the flame of iridar and peril of the starmen' in book_page.get_success_message().lower()

@pytest.mark.django_db
class TestPenNameBookEntry:
    def test_book_search_olid_to_name_fallback(self, browser, requests_mock):
        """Test book search falls back from OLID to full author name."""
        
        # Mock OpenLibrary author search response with actual results
        mock_author_search = [
            {
                "birth_date": "1892",
                "death_date": "1944",
                "key": "/authors/OL10356294A",
                "name": "Max Brand",
                "work_count": 24,
                "works": ["Young Dr. Kildare"],
                "subjects": ["Fiction", "Fiction, westerns"]
            }
        ]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=5',
            json=mock_author_search
        )

        # Mock the full author details that will be used during author creation
        mock_author_details = {
            'key': '/authors/OL10356294A',
            'name': 'Max Brand',
            'personal_name': 'Frederick Schiller Faust',
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944',
            'type': {'key': '/type/author'}
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL10356294A.json',
            json=mock_author_details
        )

        # Mock the OLID search (which will fail)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL10356294A&title=The+Mustang+Herder&limit=2',
            json={'docs': []}
        )

        # Mock the name search (which will succeed)
        mock_work_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'The Mustang Herder',
                'author_name': ['Max Brand'],
                'author_key': ['OL10356294A'],
                'first_publish_year': 1923,
                'publisher': ['G.P. Putnam\'s Sons']
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Max+Brand&title=The+Mustang+Herder&limit=2',
            json=mock_work_response
        )

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'Test Book',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'},
                'first_publish_date': '2023'
            }
        )

        # Start author search and selection
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Max Brand")
        author_page.select_openlibrary_author("Max Brand (24 works)")

        # Handle title entry
        book_page = BookPage(browser)
        book_page.enter_title("The Mustang Herder")
        book_page.submit_title_form()

        # Verify the confirmation page shows the author name
        content = browser.page_source
        assert "Max Brand" in content
        assert "The Mustang Herder" in content
        
        # Complete the entry
        book_page.confirm_title()

        # Verify work was created
        work = Work.objects.first()
        assert work is not None
        assert work.title == "The Mustang Herder"
        
        # Verify author was created with correct name
        author = work.authors.first()
        assert author is not None
        assert author.primary_name == "Max Brand"
        assert author.olid == "OL10356294A"

    def test_book_search_name_to_lastname_fallback(self, browser, requests_mock):
        """Test book search falls back from full name to last name."""
        
        # Mock OpenLibrary author search response with actual results
        mock_author_search = [
            {
                "birth_date": "1892",
                "death_date": "1944",
                "key": "/authors/OL10356294A",
                "name": "Max Brand",
                "work_count": 24,
                "works": ["Young Dr. Kildare"],
                "subjects": ["Fiction", "Fiction, westerns"]
            }
        ]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=5',
            json=mock_author_search
        )

        # Mock the full author details
        mock_author_details = {
            'name': 'Max Brand',
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944'
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL10356294A.json',
            json=mock_author_details
        )

        # Mock the OLID search (which will fail)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL10356294A&title=The+Mustang+Herder&limit=2',
            json={'docs': []}
        )

        # Mock the full name search (which will fail)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Max+Brand&title=The+Mustang+Herder&limit=2',
            json={'docs': []}
        )

        # Mock the last name search (which will succeed)
        mock_work_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'The Mustang Herder',
                'author_name': ['Max Brand'],
                'author_key': ['OL10356294A'],
                'first_publish_year': 1923,
                'publisher': ['G.P. Putnam\'s Sons']
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Brand&title=The+Mustang+Herder&limit=2',
            json=mock_work_response
        )

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'Test Book',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'},
                'first_publish_date': '2023'
            }
        )

        # Start author search and selection
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Max Brand")
        author_page.select_openlibrary_author("Max Brand (24 works)")

        # Handle title entry
        book_page = BookPage(browser)
        book_page.enter_title("The Mustang Herder")
        book_page.submit_title_form()

        # Verify the confirmation page shows the author name
        content = browser.page_source
        assert "Max Brand" in content
        assert "The Mustang Herder" in content
        
        # Complete the entry
        book_page.confirm_title()

        # Verify work was created
        work = Work.objects.first()
        assert work is not None
        assert work.title == "The Mustang Herder"
        
        # Verify author was created with correct name
        author = work.authors.first()
        assert author is not None
        assert author.primary_name == "Max Brand"
        assert author.olid == "OL10356294A"

    def test_pen_name_book_fallback_search(self, browser, requests_mock):
        """Test book search fallback when author name differs but matches through alternates."""
        
        # Create local author with just the primary name - no alternates yet
        author = Author.objects.create(
            primary_name="Max Brand",
            search_name="max brand",
            olid="OL10356294A"
            # No alternate_names - these should be discovered
        )

        # Mock the OpenLibrary work response when looking up by work_olid
        mock_work_response = {
            'key': '/works/OL123W',
            'title': 'The Mustang Herder',
            'authors': [{'key': '/authors/OL10356294A'}],  # Match our local author's OLID
            'author_name': ['Frederick Faust'],
            'author_alternative_name': [
                'Brand, Max',
                'Max Brand (pseud.)',
                'Frederick Faust',
                'George Owen Baxter'
            ]
        }
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json=mock_work_response
        )

        # Mock the OpenLibrary author search response with actual results
        mock_author_search = [
            {
                "birth_date": "1892",
                "death_date": "1944",
                "key": "/authors/OL10356294A",
                "name": "Max Brand",
                "work_count": 24,
                "works": ["Young Dr. Kildare"],
                "subjects": ["Fiction", "Fiction, westerns"]
            }
        ]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=5',
            json=mock_author_search
        )

        # Mock the full author details that will be used during author creation
        mock_author_details = {
            'key': '/authors/OL10356294A',
            'name': 'Max Brand',
            'personal_name': 'Frederick Schiller Faust',
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944',
            'type': {'key': '/type/author'}
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL10356294A.json',
            json=mock_author_details
        )

        # Mock the OLID search (which will fail)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL10356294A&title=The+Mustang+Herder&limit=2',
            json={'docs': []}
        )

        # Mock the name search (which will succeed)
        mock_work_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'The Mustang Herder',
                'author_name': ['Max Brand'],
                'author_key': ['OL10356294A'],
                'first_publish_year': 1923,
                'publisher': ['G.P. Putnam\'s Sons']
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Max+Brand&title=The+Mustang+Herder&limit=2',
            json=mock_work_response
        )

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'Test Book',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'},
                'first_publish_date': '2023'
            }
        )

        # Start author search and selection
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Max Brand")
        author_page.select_local_author("Max Brand")

        # Handle title entry
        book_page = BookPage(browser)
        book_page.enter_title("The Mustang Herder")
        book_page.submit_title_form()
        book_page.confirm_title()

        # Verify work was created with proper author
        work = Work.objects.first()
        assert work is not None
        assert work.authors.first() == author  # Should match our existing author
        assert work.olid == "OL123W"
        
        # Verify author was updated with alternate info
        author.refresh_from_db()
        assert "Frederick Faust" in author.alternate_names
        assert "Brand, Max" in author.alternate_names
        assert "Max Brand (pseud.)" in author.alternate_names
        assert "George Owen Baxter" in author.alternate_names

        # Verify success message
        assert 'added new work' in book_page.get_success_message().lower()
        assert 'the mustang herder' in book_page.get_success_message().lower()

    @pytest.mark.skip(reason="Need to implement enhanced author selection UI first")
    def test_pen_name_display_format(self, browser, requests_mock):
        """Test that author display name properly formats pen name while maintaining searchable name.
        
        NOTE: This is an initial draft. Before implementing this test fully, we need to:
        1. Update the author selection UI to show both real name and pen name
        2. Modify how we handle the author selection to parse the combined name format
        3. Implement the primary_name formatting logic
        """
        
        # Mock OpenLibrary author search response
        mock_author_search = [{
            "key": "/authors/OL10356294A",
            "name": "Frederick Schiller Faust",
            "alternate_names": ["Max Brand"],
            "birth_date": "1892",
            "death_date": "1944"
        }]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=5',
            json=mock_author_search
        )

        # Mock the full author details
        mock_author_details = {
            'key': '/authors/OL10356294A',
            'name': 'Frederick Schiller Faust',
            'alternate_names': ['Max Brand', 'George Owen Baxter'],
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944'
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL10356294A.json',
            json=mock_author_details
        )

        # Mock the work search response
        mock_work_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'The Mustang Herder',
                'author_name': ['Max Brand'],
                'author_key': ['OL10356294A'],
                'first_publish_year': 1923
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Max+Brand&title=The+Mustang+Herder&limit=2',
            json=mock_work_response
        )

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'Test Book',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'},
                'first_publish_date': '2023'
            }
        )

        # Start author search and selection
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Max Brand")
        author_page.select_openlibrary_author("Frederick Schiller Faust [also: Max Brand]")

        # Handle title entry
        book_page = BookPage(browser)
        book_page.enter_title("The Mustang Herder")
        book_page.submit_title_form()
        book_page.confirm_title()

        # Verify author was created with correct name formatting
        author = Author.objects.get(olid="OL10356294A")
        assert author.primary_name == "Frederick 'Max Brand' Faust"
        assert author.search_name == "max brand"
        assert "Max Brand" in author.alternate_names
        assert "George Owen Baxter" in author.alternate_names

        # Verify the display shows the formatted name
        assert author.display_name() == "Frederick 'Max Brand' Faust (1892-1944)"

    def test_pen_name_confirmation_display(self, browser, requests_mock):
        """Test that pen name is properly formatted on confirmation page and saved correctly."""
        
        # Mock initial OpenLibrary author search response - note this is OL10352592A
        mock_author_search = [{
            'key': '/authors/OL10352592A',  # Different OLID from what we'll get later
            'name': 'Max Brand',
            'work_count': 1636,
            'works': ["Gunman's Reckoning"],
            'subjects': ['Fiction, westerns']
        }]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=5',
            json=mock_author_search
        )
        # Also mock the confirmation page search (limit=2)
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=2',
            json=mock_author_search
        )

        # Mock the initial author details
        mock_initial_author = {
            'key': '/authors/OL10352592A',
            'name': 'Max Brand',
            'work_count': 1636
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL10352592A.json',
            json=mock_initial_author
        )

        # Mock the work search response - note this returns a different author OLID
        mock_work_response = {
            'docs': [{
                'key': '/works/OL14848834W',
                'title': 'The Mustang Herder',
                'author_name': ['Frederick Faust'],  # Different name
                'author_key': ['OL2748402A'],       # Different OLID
                'first_publish_year': 1994
            }]
        }
        
        # Mock the OLID search (which will fail)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL10352592A&title=The+Mustang+Herder&limit=2',
            json={'docs': []}
        )

        # Mock the full name search (which will fail)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Max+Brand&title=The+Mustang+Herder&limit=2',
            json={'docs': []}
        )

        # Mock the last name search (which will succeed)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Brand&title=The+Mustang+Herder&limit=2',
            json=mock_work_response
        )

        # Mock the work's author details that will be fetched during confirmation
        mock_author_details = {
            'key': '/authors/OL2748402A',
            'name': 'Frederick Faust',
            'personal_name': 'Frederick Schiller Faust',
            'alternate_names': [
                'Brand, Max',
                'George Owen Baxter',
                'Frederick Frost',
                'David Manning'
            ],
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944',
            'bio': 'American author best known by his pen name Max Brand'
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL2748402A.json',
            json=mock_author_details
        )

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'Test Book',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'},
                'first_publish_date': '2023'
            }
        )

        # Start author search
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Max Brand")

        # Instead of selecting from dropdown, submit the form to go to confirmation page
        search_form = browser.find_element(By.TAG_NAME, 'form')
        search_form.submit()

        # On confirmation page, verify the author details are displayed
        content = browser.page_source
        assert "Max Brand" in content
        assert "(1636 works)" in content
        
        # Confirm the author
        author_page.confirm_new_author()

        # Handle title entry
        book_page = BookPage(browser)
        book_page.enter_title("The Mustang Herder")
        book_page.submit_title_form()

        # Verify the confirmation page shows the formatted name
        content = browser.page_source
        assert "Frederick 'Max Brand' Faust" in content
        assert "The Mustang Herder" in content
        
        # Complete the entry
        book_page.confirm_title()

        # Verify author was updated with correct information
        author = Author.objects.get(olid="OL2748402A")  # Should now have the work's author OLID
        assert author.primary_name == "Frederick 'Max Brand' Faust"
        assert author.search_name == "max brand"  # Search name should remain the pen name
        assert "Brand, Max" in author.alternate_names
        assert "George Owen Baxter" in author.alternate_names
        assert author.birth_date == "29 May 1892"
        assert author.death_date == "12 May 1944"

        # Verify work was created and properly associated
        work = Work.objects.get(title="The Mustang Herder")
        assert work.authors.first() == author

        # Verify the original OLID author no longer exists
        with pytest.raises(Author.DoesNotExist):
            Author.objects.get(olid="OL10352592A")