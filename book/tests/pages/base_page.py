from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

class BasePage:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    def find_element(self, by, value):
        """Find an element with wait."""
        return self.wait.until(
            EC.presence_of_element_located((by, value))
        )

    def find_clickable(self, by, value):
        """Find a clickable element with wait."""
        return self.wait.until(
            EC.element_to_be_clickable((by, value))
        )

    def is_element_present(self, by, value, timeout=5):
        """Check if an element is present."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except TimeoutException:
            return False 