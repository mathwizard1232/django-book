from selenium.webdriver.common.by import By
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
        search_box = self.find_element(*self.search_input)
        search_box.clear()
        search_box.send_keys(author_name)

    def get_search_results(self):
        """Get list of search results."""
        results = self.driver.find_elements(*self.search_results)
        return [result.text for result in results]

    def select_author(self, author_name):
        """Select an author from the results."""
        results = self.driver.find_elements(*self.search_results)
        for result in results:
            if author_name in result.text:
                result.click()
                break 