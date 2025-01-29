import pytest
from django.urls import reverse
from book.models import Location, Room, Bookcase, Shelf, Work, Edition, Copy, Author
from .pages.location_page import LocationPage
from .pages.author_page import AuthorPage
from .pages.book_page import BookPage
from selenium.webdriver.common.by import By

@pytest.mark.django_db
class TestLocationManagement:
    def test_create_basic_location_hierarchy(self, browser):
        """Test creating a basic location hierarchy: Building -> Room -> Bookcase with shelves"""
        location_page = LocationPage(browser)
        location_page.navigate()

        # Create building
        location_page.create_building("Test House")
        location = Location.objects.get(name="Test House")
        assert location.type == "HOUSE"

        # Create room
        location_page.create_room("Study", location.name)
        room = Room.objects.get(name="Study")
        assert room.location == location

        # Create bookcase with 5 shelves
        location_page.create_bookcase("North Wall Bookcase", room.name, 5)
        bookcase = Bookcase.objects.get(name="North Wall Bookcase")
        assert bookcase.room == room
        assert bookcase.shelf_count == 5

        # Verify shelves were created
        shelves = Shelf.objects.filter(bookcase=bookcase).order_by('position')
        assert len(shelves) == 5
        assert [s.position for s in shelves] == [1, 2, 3, 4, 5]

    def test_shelve_new_book(self, browser, requests_mock):
        """Test shelving a newly added book"""
        # First create a basic location hierarchy
        location = Location.objects.create(name="Test House", type="HOUSE")
        room = Room.objects.create(name="Study", location=location)
        bookcase = Bookcase.objects.create(name="North Wall Bookcase", room=room, shelf_count=5)
        shelf = Shelf.objects.get(bookcase=bookcase, position=1)

        # Verify hierarchy exists
        print("\nVerifying location hierarchy:")
        print(f"Location: {Location.objects.first()}")
        print(f"Room: {Room.objects.first()}")
        print(f"Bookcase: {Bookcase.objects.first()}")
        print(f"Shelf: {Shelf.objects.first()}")

        # Create test author and work
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
        
        # Mock the search endpoint
        requests_mock.get(
            'https://openlibrary.org/search.json?title=Test+Book&author=OL123A',
            json=mock_work_response
        )
        
        # Mock the work details endpoint
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'Test Book',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'}
            }
        )

        # Add book and get to shelving page
        from .pages.author_page import AuthorPage
        from .pages.book_page import BookPage

        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Test")
        author_page.select_local_author("Test Author")

        book_page = BookPage(browser)
        book_page.enter_title("Test Book")
        book_page.submit_title_form()

        # Check dropdown states
        print("\nChecking dropdown states:")
        location_select = browser.find_element(By.ID, 'location-1')
        print("Location options:", [opt.text for opt in location_select.find_elements(By.TAG_NAME, 'option')])
        print("Location selected index:", location_select.get_property('selectedIndex'))

        room_select = browser.find_element(By.ID, 'room-1')
        print("Room options:", [opt.text for opt in room_select.find_elements(By.TAG_NAME, 'option')])
        print("Room selected index:", room_select.get_property('selectedIndex'))

        bookcase_select = browser.find_element(By.ID, 'bookcase-1')
        print("Bookcase options:", [opt.text for opt in bookcase_select.find_elements(By.TAG_NAME, 'option')])
        print("Bookcase selected index:", bookcase_select.get_property('selectedIndex'))

        print("\nBefore shelf selection:")
        print(f"Current URL: {browser.current_url}")
        print("Page title:", browser.title)

        # The location hierarchy should be auto-selected since there's only one option
        # But we still need to select a shelf
        book_page.select_shelf(f"Shelf {shelf.position}")
        book_page.confirm_shelving()

        # Verify book was shelved correctly
        copy = Copy.objects.first()
        assert copy.shelf == shelf
        assert copy.bookcase == bookcase
        assert copy.room == room
        assert copy.location == location 

    def test_shelve_double_book(self, browser, requests_mock):
        """Test shelving a double book (collection work) after creation."""
        # First create a basic location hierarchy
        location = Location.objects.create(name="Test House", type="HOUSE")
        room = Room.objects.create(name="Study", location=location)
        bookcase = Bookcase.objects.create(name="North Wall Bookcase", room=room, shelf_count=5)
        shelf = Shelf.objects.get(bookcase=bookcase, position=1)

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

        # Mock OpenLibrary API responses
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
        
        # Mock the API calls
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL123A&title=The+Flame+of+Iridar&limit=2',
            json=flame_response
        )
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL456A&title=Peril+of+the+Starmen&limit=2',
            json=peril_response
        )
        
        # Add work details mocks
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'The Flame of Iridar',
                'authors': [{'key': '/authors/OL123A'}],
                'type': {'key': '/type/work'}
            }
        )
        requests_mock.get(
            'https://openlibrary.org/works/OL456W.json',
            json={
                'key': '/works/OL456W',
                'title': 'Peril of the Starmen',
                'authors': [{'key': '/authors/OL456A'}],
                'type': {'key': '/type/work'}
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
        book_page.mark_as_collection()
        
        # Select second work's author
        author_page.search_author("Kris Neville")
        author_page.select_local_author("Kris Neville")
        
        # Enter second work's title
        book_page.enter_title("Peril of the Starmen")
        book_page.submit_title_form()
        
        # Fix titles and confirm collection
        book_page.modify_second_work_title("Peril of the Starmen")
        book_page.modify_collection_title("The Flame of Iridar and Peril of the Starmen")
        
        # Debug - check dropdown states before selecting shelf
        print("\nChecking dropdown states:")
        location_select = browser.find_element(By.ID, 'location-1')
        print("Location options:", [opt.text for opt in location_select.find_elements(By.TAG_NAME, 'option')])
        print("Location selected index:", location_select.get_property('selectedIndex'))

        room_select = browser.find_element(By.ID, 'room-1')
        print("Room options:", [opt.text for opt in room_select.find_elements(By.TAG_NAME, 'option')])
        print("Room selected index:", room_select.get_property('selectedIndex'))

        bookcase_select = browser.find_element(By.ID, 'bookcase-1')
        print("Bookcase options:", [opt.text for opt in bookcase_select.find_elements(By.TAG_NAME, 'option')])
        print("Bookcase selected index:", bookcase_select.get_property('selectedIndex'))

        # Select shelf and confirm
        book_page.select_shelf(f"Shelf {shelf.position}")
        book_page.confirm_shelving()

        # Verify collection was created correctly
        collection = Work.objects.filter(type="COLLECTION").first()
        assert collection is not None
        assert collection.title == "The Flame of Iridar and Peril of the Starmen"

        # Verify only one copy exists and it's for the collection
        copies = Copy.objects.all()
        assert len(copies) == 1
        copy = copies[0]
        
        # Verify the copy is associated with the collection work (not component works)
        assert copy.edition.work == collection
        
        # Verify copy location hierarchy
        assert copy.shelf == shelf
        assert copy.bookcase == bookcase
        assert copy.room == room
        assert copy.location == location

        # Verify component works exist but have no copies
        flame = Work.objects.filter(title="The Flame of Iridar").first()
        peril = Work.objects.filter(title="Peril of the Starmen").first()
        assert flame is not None
        assert peril is not None
        assert not Copy.objects.filter(edition__work=flame).exists()
        assert not Copy.objects.filter(edition__work=peril).exists() 