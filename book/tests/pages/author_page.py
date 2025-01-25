from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base_page import BasePage

class AuthorPage(BasePage):
    def __init__(self, driver):
        super().__init__(driver)
        self.url = '/author/'
        self.search_input = (By.CLASS_NAME, 'basicAutoComplete')
        self.search_results = (By.CLASS_NAME, 'dropdown-item')

    def navigate(self):
        """Navigate to the author search page."""
        self.driver.get(self.driver.current_url.split('#')[0] + self.url)

    def search_author(self, author_name):
        """Search for an author."""
        # Wait for autocomplete to be initialized
        self.wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'basicAutoComplete'))
        )
        
        search_box = self.find_element(*self.search_input)
        search_box.clear()
        search_box.send_keys(author_name)

    def get_search_results(self):
        """Get list of search results."""
        results = self.driver.find_elements(*self.search_results)
        return [result.text for result in results]

    def select_local_author(self, author_name):
        """Select a local author from the dropdown."""
        print(f"\nStarting local author selection for: {author_name}")
        
        # Wait for dropdown items to appear
        self.wait.until(
            EC.presence_of_all_elements_located(self.search_results)
        )
        
        # Find and click the result
        results = self.driver.find_elements(*self.search_results)
        print(f"Found {len(results)} dropdown items")
        print(f"Dropdown texts: {[r.text for r in results]}")
        
        for result in results:
            if author_name in result.text:
                print(f"Found matching result: {result.text}")
                print("Current URL before click:", self.driver.current_url)
                self.driver.execute_script("arguments[0].click();", result)
                break
        
        # Wait for redirect to title page
        print("Waiting for redirect to /title")
        try:
            self.wait.until(
                EC.url_contains('/title')
            )
            print("Successfully redirected to:", self.driver.current_url)
        except Exception as e:
            print("Failed to redirect. Current URL:", self.driver.current_url)
            print("Page source:", self.driver.page_source[:500])
            raise

    def confirm_new_author(self):
        """Confirm a new author on the confirmation page."""
        submit_button = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input.btn.btn-primary"))
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
        
        results = self.driver.find_elements(*self.search_results)
        found = False
        for result in results:
            if result.text == display_name:
                print(f"Found matching result: {result.text}")
                print("Current URL before click:", self.driver.current_url)
                self.driver.execute_script("arguments[0].click();", result)
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