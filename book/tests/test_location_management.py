import pytest
from django.urls import reverse
from book.models import Location, Room, Bookcase, Shelf, Work, Edition, Copy, Author
from .pages.location_page import LocationPage
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
        
        # Mock OpenLibrary API response
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