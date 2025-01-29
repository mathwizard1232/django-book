from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_page import BasePage

class AuthorPage(BasePage):
    url = '/author/'
    
    def __init__(self, browser):
        super().__init__(browser)  # Call parent constructor
        self.search_input = (By.ID, 'id_author_name')
        self.search_button = (By.CSS_SELECTOR, 'button[type="submit"]')
        self.local_author_link = (By.CLASS_NAME, 'local-author')
        self.openlibrary_author_link = (By.CLASS_NAME, 'openlibrary-author')
        self.confirm_button = (By.ID, 'confirm-author')
        self.search_results = (By.CLASS_NAME, 'dropdown-item')

    def navigate(self):
        """Navigate to the author search page."""
        self.browser.get(self.browser.current_url.split('#')[0] + self.url)

    def search_author(self, name):
        """Enter an author name in the search box (does not submit)."""
        print(f"\nEntering author search text: {name}")
        search_box = self.find_element(*self.search_input)
        search_box.clear()
        search_box.send_keys(name)

    def get_search_results(self):
        """Get list of search results."""
        results = self.browser.find_elements(*self.search_results)
        return [result.text for result in results]

    def select_local_author(self, author_name):
        """Select a local author from the dropdown."""
        print(f"\nStarting local author selection for: {author_name}")
        
        # Wait for dropdown items to appear
        self.wait.until(
            EC.presence_of_all_elements_located(self.search_results)
        )
        
        # Find and click the result
        results = self.browser.find_elements(*self.search_results)
        print(f"Found {len(results)} dropdown items")
        print(f"Dropdown texts: {[r.text for r in results]}")
        
        for result in results:
            if author_name in result.text:
                print(f"Found matching result: {result.text}")
                print("Current URL before click:", self.browser.current_url)
                self.browser.execute_script("arguments[0].click();", result)
                break
        
        # Wait for redirect to title page
        print("Waiting for redirect to /title")
        try:
            self.wait.until(
                EC.url_contains('/title')
            )
            print("Successfully redirected to:", self.browser.current_url)
        except Exception as e:
            print("Failed to redirect. Current URL:", self.browser.current_url)
            print("Page source:", self.browser.page_source[:500])
            raise

    def confirm_new_author(self):
        """Confirm a new author on the confirmation page."""
        submit_button = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.btn-primary"))
        )
        submit_button.click()
        
        # Wait for redirect to title page
        self.wait.until(
            EC.url_contains('/title')
        )

    def select_openlibrary_author(self, display_name):
        """Select an OpenLibrary author from the dropdown by their display name."""
        self.wait.until(
            EC.presence_of_all_elements_located(self.search_results)
        )
        
        results = self.browser.find_elements(*self.search_results)
        found = False
        for result in results:
            if result.text == display_name:
                print(f"Found matching result: {result.text}")
                print("Current URL before click:", self.browser.current_url)
                self.browser.execute_script("arguments[0].click();", result)
                found = True
                break
        
        if not found:
            print(f"\nFailed to find exact match for '{display_name}'")
            print("Available options:")
            for r in results:
                print(f"- '{r.text}'")
            raise ValueError(f"Could not find author option matching '{display_name}'")

        # Wait for redirect to title page
        self.wait.until(
            EC.url_contains('/title')
        ) 