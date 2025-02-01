import pytest
from django.urls import reverse
from book.models import Location, Room, Bookcase, Shelf, Bookcase, Work, Edition, Copy, Author
from book.tests.pages.author_page import AuthorPage
from book.tests.pages.book_page import BookPage

@pytest.mark.django_db
class TestListDisplay:
    def test_collection_work_display(self, client):
        """Test that a shelved collection work displays correctly without unassigned entries."""
        # Create basic location hierarchy
        location = Location.objects.create(name="Test House", type="HOUSE")
        room = Room.objects.create(name="Study", location=location)
        bookcase = Bookcase.objects.create(name="North Wall Bookcase", room=room, shelf_count=5)
        shelf = Shelf.objects.get(bookcase=bookcase, position=1)

        # Create test authors
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

        # Create the collection work and its components
        collection = Work.objects.create(
            title="The Flame of Iridar and Peril of the Starmen",
            search_name="flame of iridar and peril of starmen",
            type="COLLECTION"
        )
        collection.authors.add(carter, neville)

        # Create component works
        flame = Work.objects.create(
            title="The Flame of Iridar",
            search_name="flame of iridar",
            type="NOVEL"
        )
        flame.authors.add(carter)

        peril = Work.objects.create(
            title="Peril of the Starmen",
            search_name="peril of starmen",
            type="NOVEL"
        )
        peril.authors.add(neville)

        # Link components to collection
        collection.component_works.add(flame, peril)

        # Create edition and copy for the collection
        edition = Edition.objects.create(
            work=collection,
            publisher="Unknown",
            format="PAPERBACK"
        )

        copy = Copy.objects.create(
            edition=edition,
            shelf=shelf,
            location=location,
            room=room,
            bookcase=bookcase,
            condition="GOOD"
        )

        # Get the list view
        response = client.get(reverse('list'))
        content = response.content.decode()

        # Add before line 92:
        print("Content:", content)

        # Verify the collection appears in the correct location
        assert f"{location.name}" in content
        assert f"{bookcase.name}" in content
        assert f"Shelf {shelf.position}" in content
        assert collection.title in content

        # Verify authors are displayed correctly
        assert "Lin Carter" in content
        assert "Kris Neville" in content

        # Verify component works don't appear as unassigned
        assert "Unassigned Works" not in content
        
        # Check that component works don't appear as separate entries
        # Look for the titles with surrounding elements that would indicate a separate entry
        assert f'<li>{flame.title}</li>' not in content  # Component work shouldn't appear separately
        assert f'<li>{peril.title}</li>' not in content  # Component work shouldn't appear separately

        # Verify work counts are correct
        assert ">1</h3>" in content and "Distinct Works" in content  # Should only count the collection as one work 

    def test_pen_name_display_without_recursion(self, client):
        """Test that a pen name author displays correctly without recursive formatting."""
        # Create basic location hierarchy
        location = Location.objects.create(name="Test House", type="HOUSE")
        room = Room.objects.create(name="Study", location=location)
        bookcase = Bookcase.objects.create(name="North Wall Bookcase", room=room, shelf_count=5)
        shelf = Shelf.objects.get(bookcase=bookcase, position=1)

        # Create test author with pen name format
        author = Author.objects.create(
            primary_name="Frederick 'Max Brand' Faust",
            search_name="max brand",
            olid="OL123A",
            alternate_names=["Max Brand", "George Owen Baxter"]
        )

        # Create work
        work = Work.objects.create(
            title="The Mustang Herder",
            search_name="mustang herder",
            type="NOVEL"
        )
        work.authors.add(author)

        # Create edition and copy
        edition = Edition.objects.create(
            work=work,
            publisher="Unknown",
            format="PAPERBACK"
        )

        copy = Copy.objects.create(
            edition=edition,
            shelf=shelf,
            location=location,
            room=room,
            bookcase=bookcase,
            condition="GOOD"
        )

        # Get the list view
        response = client.get(reverse('list'))
        content = response.content.decode()

        # Add debug output
        print("Content:", content)

        # Verify the author name appears correctly once (accounting for HTML encoding)
        assert "Frederick &#x27;Max Brand&#x27; Faust" in content
        assert "Frederick &#x27;Frederick &#x27;Max Brand&#x27; Faust&#x27; Faust" not in content

        # Verify work displays correctly
        assert work.title in content
        assert f"{location.name}" in content
        assert f"{bookcase.name}" in content
        assert f"Shelf {shelf.position}" in content 

    def test_pen_name_integration_display(self, client, browser, requests_mock):
        """Test pen name display through the complete flow: author creation -> work entry -> list view."""
        # First create a basic location hierarchy
        location = Location.objects.create(name="Test House", type="HOUSE")
        room = Room.objects.create(name="Study", location=location)
        bookcase = Bookcase.objects.create(name="North Wall Bookcase", room=room, shelf_count=5)
        shelf = Shelf.objects.get(bookcase=bookcase, position=1)

        # Mock OpenLibrary author search response
        mock_author_search = [{
            "key": "/authors/OL10356294A",
            "name": "Frederick Schiller Faust",
            "alternate_names": ["Max Brand"],
            "birth_date": "1892",
            "death_date": "1944",
            "work_count": 100
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
                'author_name': ['Frederick Faust'],  # Note: Different name format
                'author_key': ['OL10356294A'],
                'first_publish_year': 1923
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Frederick+Schiller+Faust&title=The+Mustang+Herder&limit=2',
            json=mock_work_response
        )

        # Mock the OLID search (which will fail)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL10356294A&title=The+Mustang+Herder&limit=2',
            json={'docs': []}
        )

        # Mock the name search (which will succeed)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Max+Brand&title=The+Mustang+Herder&limit=2',
            json=mock_work_response
        )

        # Mock the work details API
        requests_mock.get(
            'https://openlibrary.org/works/OL123W.json',
            json={
                'key': '/works/OL123W',
                'title': 'The Mustang Herder',
                'authors': [{'key': '/authors/OL10356294A'}],
                'type': {'key': '/type/work'}
            }
        )

        # Start author search and selection
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Max Brand")
        author_page.select_openlibrary_author("Frederick Schiller Faust (100 works)")

        # Handle title entry
        book_page = BookPage(browser)
        book_page.enter_title("The Mustang Herder")
        book_page.submit_title_form()

        # Verify the confirmation page shows the formatted name correctly
        content = browser.page_source
        assert "Frederick 'Max Brand' Faust" in content
        assert "The Mustang Herder" in content

        # Select shelf and confirm
        book_page.select_shelf(f"Shelf {shelf.position}")
        book_page.confirm_shelving()

        # Now get the list view
        response = client.get(reverse('list'))
        content = response.content.decode()
        
        print("\nList view content:")
        print(content)

        # Verify the author name appears correctly exactly twice (once in authors list, once in works list)
        assert content.count("Frederick &#x27;Max Brand&#x27; Faust") == 2
        assert "Frederick &#x27;Frederick &#x27;Max Brand&#x27; Faust&#x27; Faust" not in content

        # Verify other display elements
        assert "The Mustang Herder" in content
        assert f"{location.name}" in content
        assert f"{bookcase.name}" in content
        assert f"Shelf {shelf.position}" in content

        # Verify the database state
        author = Author.objects.get(olid="OL10356294A")
        assert author.primary_name == "Frederick 'Max Brand' Faust"
        assert author.search_name == "max brand"
        assert "Max Brand" in author.alternate_names
        assert "George Owen Baxter" in author.alternate_names 

    def test_pen_name_double_formatting_integration(self, client, browser, requests_mock):
        """Test that pen name formatting doesn't get applied twice through the complete flow."""
        # Create basic location hierarchy
        location = Location.objects.create(name="Test House", type="HOUSE")
        room = Room.objects.create(name="Study", location=location)
        bookcase = Bookcase.objects.create(name="North Wall Bookcase", room=room, shelf_count=5)
        shelf = Shelf.objects.get(bookcase=bookcase, position=1)

        # Mock OpenLibrary author search response - initial "Max Brand" search
        mock_author_search = [{
            "key": "/authors/OL10356294A",
            "name": "Max Brand",
            "work_count": 24
        }]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=5',
            json=mock_author_search
        )

        # Mock the initial author details
        mock_initial_author = {
            'key': '/authors/OL10356294A',
            'name': 'Max Brand',
            'work_count': 24
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL10356294A.json',
            json=mock_initial_author
        )
        # Mock the OLID search (which will fail)
        requests_mock.get(
            'https://openlibrary.org/search.json?author=OL10356294A&title=The+Mustang+Herder&limit=2',
            json={'docs': []}
        )

        # Mock the work search that returns Frederick Faust as author
        mock_work_response = {
            'docs': [{
                'key': '/works/OL123W',
                'title': 'The Mustang Herder',
                'author_name': ['Frederick Faust'],
                'author_key': ['OL2748402A'],
                'first_publish_year': 1923
            }]
        }
        requests_mock.get(
            'https://openlibrary.org/search.json?author=Max+Brand&title=The+Mustang+Herder&limit=2',
            json=mock_work_response
        )

        # Mock the work's author details that will be fetched
        mock_author_details = {
            'key': '/authors/OL2748402A',
            'name': 'Frederick Faust',
            'personal_name': 'Frederick Schiller Faust',
            'alternate_names': ['Max Brand', 'George Owen Baxter'],
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944'
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
                'title': 'The Mustang Herder',
                'authors': [{'key': '/authors/OL2748402A'}],
                'type': {'key': '/type/work'}
            }
        )

        # Start the flow - author search
        author_page = AuthorPage(browser)
        author_page.navigate()
        author_page.search_author("Max Brand")
        author_page.select_openlibrary_author("Max Brand (24 works)")

        # Handle title entry
        book_page = BookPage(browser)
        book_page.enter_title("The Mustang Herder")
        book_page.submit_title_form()

        # Debug output for confirmation page
        print("\nConfirmation page content:")
        print(browser.page_source)

        # Verify the confirmation page shows the formatted name
        content = browser.page_source
        assert "Frederick 'Max Brand' Faust" in content
        assert "The Mustang Herder" in content

        # Select shelf and confirm
        book_page.select_shelf(f"Shelf {shelf.position}")
        book_page.confirm_shelving()

        # Now get the list view
        response = client.get(reverse('list'))
        content = response.content.decode()
        
        print("\nList view content:")
        print(content)

        # Verify the author name appears correctly exactly twice
        assert content.count("Frederick &#x27;Max Brand&#x27; Faust") == 2
        assert "Frederick &#x27;Frederick &#x27;Max Brand&#x27; Faust&#x27; Faust" not in content

        # Verify other display elements
        assert "The Mustang Herder" in content
        assert f"{location.name}" in content
        assert f"{bookcase.name}" in content
        assert f"Shelf {shelf.position}" in content

        # Verify final database state
        author = Author.objects.get(olid="OL2748402A")
        assert author.primary_name == "Frederick 'Max Brand' Faust"
        assert author.search_name == "max brand"
        assert "Max Brand" in author.alternate_names
        assert "George Owen Baxter" in author.alternate_names 