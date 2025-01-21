import pytest
from django.urls import reverse
from book.models import Location, Room, Bookcase, Shelf, Work, Edition, Copy, Author

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