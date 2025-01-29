from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

class BasePage:
    def __init__(self, browser):
        self.browser = browser
        # Reduce default wait time for tests
        self.wait = WebDriverWait(browser, timeout=2)  # Down from default 10

    def wait_for(self, condition, message=None):
        """Custom wait method with better error handling."""
        try:
            return self.wait.until(condition)
        except TimeoutException as e:
            print("\n=== Page Content at Time of Failure ===")
            print(f"Current URL: {self.browser.current_url}")
            print("\nPage Source:")
            print(self.browser.page_source)
            print("\n=== End Page Content ===")
            if message:
                raise TimeoutException(f"{message}\n{str(e)}")
            raise

    def find_element(self, by, value):
        """Find an element with wait and debug output."""
        return self.wait_for(
            EC.presence_of_element_located((by, value)),
            f"Could not find element: {by}={value}"
        )

    def find_clickable(self, by, value):
        """Find a clickable element with wait and debug output."""
        return self.wait_for(
            EC.element_to_be_clickable((by, value)),
            f"Element not clickable: {by}={value}"
        )

    def is_element_present(self, by, value, timeout=5):
        """Check if an element is present with debug output."""
        try:
            WebDriverWait(self.browser, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except TimeoutException:
            print("\n=== Element Not Found ===")
            print(f"Looking for: {by}={value}")
            print(f"Current URL: {self.browser.current_url}")
            print("\nPage Source:")
            print(self.browser.page_source)
            print("\n=== End Debug Output ===")
            return False

    def select_dropdown(self, by, value, option_text):
        """Select an option from a dropdown by visible text."""
        dropdown = self.wait_for(
            EC.presence_of_element_located((by, value)),
            f"Dropdown not found: {by}={value}"
        )
        self.wait_for(
            EC.element_to_be_clickable((by, value)),
            f"Dropdown not clickable: {by}={value}"
        )
        
        from selenium.webdriver.support.ui import Select
        select = Select(dropdown)
        try:
            select.select_by_visible_text(option_text)
        except Exception as e:
            print("\n=== Dropdown Selection Failed ===")
            print(f"Available options: {[o.text for o in select.options]}")
            print(f"Attempted to select: {option_text}")
            raise 