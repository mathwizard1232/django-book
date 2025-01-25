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

        # Select the author and verify redirect to title page
        page.select_openlibrary_author("Frederick Faust [also: Max Brand (pseud.)]")
        
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
            'type': {'key': '/type/author'}
        }, {
            'key': '/authors/OL9999999A',
            'name': 'Max Brand',
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

        # Verify dates are present in the result text
        result_texts = [r.text for r in results]
        assert any("Max Brand (1892-1944)" in text for text in result_texts)
        assert any("Max Brand" in text and "(1892-1944)" not in text for text in result_texts)

        # Select the author and verify redirect to title page
        page.select_openlibrary_author("Max Brand (1892-1944)")
        
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