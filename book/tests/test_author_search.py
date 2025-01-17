import pytest
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from book.models.author import Author
from book.tests.pages.author_page import AuthorPage
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