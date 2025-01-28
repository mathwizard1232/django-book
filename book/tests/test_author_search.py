import pytest
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from book.models.author import Author
from book.tests.pages.author_page import AuthorPage
from book.tests.pages.book_page import BookPage
import time

@pytest.mark.django_db
class TestAuthorSearch:
    def test_author_search_local(self, browser):
        """Test searching for a local author."""
        # Create test author in database
        Author.objects.create(
            primary_name="Test Author",
            search_name="test author",
            olid="OL123A"
        )

        # Initialize page and perform search
        page = AuthorPage(browser)
        page.navigate()
        page.search_author("Test")

        # Wait for and verify results
        wait = WebDriverWait(browser, 10)
        results = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "dropdown-item"))
        )
        result_texts = [r.text for r in results]
        assert any("Test Author" in result for result in result_texts)

    def test_author_search_openlibrary(self, browser, requests_mock):
        """Test searching for an author via OpenLibrary."""
        # Mock OpenLibrary API response
        mock_response = [{
            'key': '/authors/OL123A',
            'name': 'Jane Doe',
            'work_count': 10,
            'type': {'key': '/type/author'}
        }]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Jane&limit=5',
            json=mock_response
        )

        # Initialize page and perform search
        page = AuthorPage(browser)
        page.navigate()
        page.search_author("Jane")

        # Wait for and verify results
        wait = WebDriverWait(browser, 10)
        results = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "dropdown-item"))
        )
        result_texts = [r.text for r in results]
        assert any("Jane Doe" in result for result in result_texts)

    def test_author_search_pen_name(self, browser, requests_mock):
        """Test searching for an author by pen name."""
        # Mock OpenLibrary API response with pen name info
        mock_response = [{
            'key': '/authors/OL2748402A',
            'name': 'Frederick Faust',
            'work_count': 100,
            'alternate_names': ['Max Brand (pseud.)', 'George Owen Baxter'],
            'type': {'key': '/type/author'}
        }]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=5',
            json=mock_response
        )

        # Mock the full author details that will be fetched for confirmation
        mock_author_details = {
            'name': 'Frederick Faust',
            'personal_name': 'Frederick Schiller Faust',
            'alternate_names': ['Max Brand (pseud.)', 'George Owen Baxter'],
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944'
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL2748402A.json',
            json=mock_author_details
        )

        # Initialize page and perform search
        page = AuthorPage(browser)
        page.navigate()
        page.search_author("Max Brand")

        # Wait for and verify results
        wait = WebDriverWait(browser, 10)
        results = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "dropdown-item"))
        )
        result_texts = [r.text for r in results]

        # After getting results
        print("\nFound result elements:")
        for result in results:
            print(f"- Text: '{result.text}'")
            print(f"- HTML: '{result.get_attribute('innerHTML')}'")

        # Verify both names appear in the results
        assert any("Frederick Faust" in result for result in result_texts), f"Frederick Faust not found in results: {result_texts}"
        assert any("Max Brand" in result for result in result_texts), f"Max Brand not found in results: {result_texts}"

        # Update selection to match the new display format that includes pen name
        page.select_openlibrary_author("Frederick Faust (100 works) [also: Max Brand (pseud.)]")

        # Wait for and verify redirect to title page
        wait.until(
            EC.url_contains('/title')
        )
        content = browser.page_source
        assert "Frederick Faust" in content

    def test_author_search_display_details(self, browser, requests_mock):
        """Test that author search results show distinguishing details."""
        # Mock OpenLibrary API response with two Max Brand entries
        mock_response = [{
            'key': '/authors/OL2748402A',
            'name': 'Max Brand',
            'birth_date': '1892',
            'death_date': '1944',
            'personal_name': 'Frederick Faust',
            'alternate_names': ['Frederick Faust'],
            'work_count': 100,  # Higher work count should be shown
            'type': {'key': '/type/author'}
        }, {
            'key': '/authors/OL9999999A',
            'name': 'Max Brand',
            'work_count': 5,  # Lower work count might not be shown
            'type': {'key': '/type/author'}
        }]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=5',
            json=mock_response
        )

        # Mock the full author details
        mock_author_details = {
            'name': 'Max Brand',
            'personal_name': 'Frederick Schiller Faust',
            'alternate_names': ['Frederick Faust'],
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944'
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL2748402A.json',
            json=mock_author_details
        )

        # Initialize page and perform search
        page = AuthorPage(browser)
        page.navigate()
        page.search_author("Max Brand")

        # Wait for and verify results
        wait = WebDriverWait(browser, 10)
        results = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "dropdown-item"))
        )

        # Debug logging
        print("\nDropdown items found:", len(results))
        for idx, result in enumerate(results):
            print(f"Result {idx} text:", result.text)
            print(f"Result {idx} HTML:", result.get_attribute('innerHTML'))

        # Verify results show distinguishing details
        result_texts = [r.text for r in results]
        
        # First result should show work count
        assert result_texts[0] == "Max Brand (100 works)"
        
        # Second result should be just the name
        assert result_texts[1] == "Max Brand"

        # Select the author and verify redirect to title page
        page.select_openlibrary_author("Max Brand (100 works)")
        
        # Wait for and verify the title page content
        wait.until(
            EC.url_contains('/title')
        )
        content = browser.page_source
        assert "Max Brand" in content

    def test_author_search_local_display(self, browser):
        """Test that local author search results show distinguishing details."""
        # Create test authors in database with similar names
        Author.objects.create(
            primary_name="John Smith",
            search_name="john smith",
            olid="OL123A",
            birth_date="1900",
            death_date="1980"
        )
        Author.objects.create(
            primary_name="John Smith",
            search_name="john smith",
            olid="OL456A"
        )

        # Initialize page and perform search
        page = AuthorPage(browser)
        page.navigate()
        page.search_author("John Smith")

        # Wait for and verify results
        wait = WebDriverWait(browser, 10)
        results = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "dropdown-item"))
        )
        
        # Debug logging
        print("\nDropdown items found:", len(results))
        for idx, result in enumerate(results):
            print(f"Result {idx} text:", result.text)
            print(f"Result {idx} HTML:", result.get_attribute('innerHTML'))
        
        # Verify dates are present in the result text
        result_texts = [r.text for r in results]
        assert any("John Smith (1900-1980)" in text for text in result_texts)
        assert any("John Smith" in text and "(1900-1980)" not in text for text in result_texts)

    def test_author_search_result_ranking(self, browser, requests_mock):
        """Test that author search results are properly ranked and best match is selected."""
        # Mock OpenLibrary API response with multiple results of varying quality
        mock_response = [
            {
                "key": "/authors/OL12946735A",
                "name": "Max Brand Max Brand",
                "work_count": 2,
                "works": ["Ronicky Doone Illustared"],
                "subjects": []
            },
            {
                "key": "/authors/OL10352592A",
                "name": "Max Brand",
                "work_count": 1636,
                "works": ["Gunman's Reckoning Illustrated"],
                "subjects": [
                    "Fiction, westerns",
                    "Fiction, general",
                    "Frontier and pioneer life, fiction"
                ]
            },
            {
                "birth_date": "1892",
                "death_date": "1944",
                "key": "/authors/OL10356294A",
                "name": "Max Brand",
                "work_count": 24,
                "works": ["Young Dr. Kildare"],
                "subjects": ["Fiction", "Fiction, westerns"]
            },
            {
                "key": "/authors/OL10510226A",
                "name": "Max brand",
                "work_count": 16,
                "works": ["Valley Thieves"],
                "subjects": []
            },
            {
                "key": "/authors/OL12236824A",
                "name": "max brand",
                "work_count": 2,
                "works": ["Valley Vultures"],
                "subjects": []
            }
        ]
        requests_mock.get(
            'https://openlibrary.org/authors/_autocomplete?q=Max+Brand&limit=5',
            json=mock_response
        )

        # Mock the full author details for the best match
        mock_author_details = {
            'key': '/authors/OL10352592A',
            'name': 'Frederick Schiller Faust',
            'personal_name': 'Frederick Schiller Faust',
            'alternate_names': ['Max Brand', 'George Owen Baxter'],
            'birth_date': '29 May 1892',
            'death_date': '12 May 1944',
            'bio': 'American author best known by his pen name Max Brand'
        }
        requests_mock.get(
            'https://openlibrary.org/authors/OL10352592A.json',
            json=mock_author_details
        )

        # Initialize page and perform search
        page = AuthorPage(browser)
        page.navigate()
        page.search_author("Max Brand")

        # Wait for and verify results
        wait = WebDriverWait(browser, 10)
        results = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "dropdown-item"))
        )

        # Verify results are properly ranked
        result_texts = [r.text for r in results]
        
        # The entry with high work count should be first
        assert "Max Brand" in result_texts[0]
        assert "(1636 works)" in result_texts[0]
        
        # The entry with birth/death dates should be second
        assert "Max Brand" in result_texts[1]
        
        # Verify that selecting the top result automatically redirects to title page
        # (since it's a high-confidence match with high work count)
        page.select_openlibrary_author(result_texts[0])
        
        # Should skip confirmation and go straight to title
        wait.until(EC.url_contains('/title'))
        
        # Verify the author was created locally with complete information
        author = Author.objects.get(olid="OL10352592A")
        assert author.primary_name == "Frederick 'Max Brand' Faust"
        assert author.search_name == "max brand"
        assert author.birth_date == "29 May 1892"
        assert author.death_date == "12 May 1944"
        assert "Max Brand" in author.alternate_names
        assert "George Owen Baxter" in author.alternate_names 