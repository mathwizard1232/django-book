from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base_page import BasePage

class ISBNPage(BasePage):
    def __init__(self, browser):
        super().__init__(browser)
        self.url = '/isbn/'
        self.isbn_input = (By.NAME, 'isbn')
        self.submit_button = (By.CSS_SELECTOR, 'button[type="submit"]')
        self.success_alert = (By.CLASS_NAME, 'alert-success')
        
        # Add selectors for confirm-book.html page
        self.confirm_without_shelving = (By.CSS_SELECTOR, 'input[value="Confirm Without Shelving"]')
        
    def navigate(self):
        """Navigate to the ISBN entry page."""
        self.browser.get(self.browser.current_url.split('#')[0] + self.url)
        
    def enter_isbn(self, isbn):
        """Enter an ISBN."""
        isbn_field = self.find_element(*self.isbn_input)
        isbn_field.clear()
        isbn_field.send_keys(isbn)
        
    def confirm_isbn(self):
        """Submit the ISBN and handle the confirmation page."""
        print("\nStarting ISBN confirmation")
        
        # First submit the ISBN form
        submit = self.find_clickable(*self.submit_button)
        print(f"Found submit button: {submit.get_attribute('value')}")
        submit.click()
        print("Clicked submit button")
        
        # Now we should be on confirm-book.html
        # Wait for and click the confirm without shelving button
        confirm_final = self.find_clickable(*self.confirm_without_shelving)
        print("Found final confirm button")
        confirm_final.click()
        print("Clicked final confirm button")
        
        # Wait for success alert
        self.wait.until(
            EC.presence_of_element_located(self.success_alert)
        )
        print("Found success alert")
        
    def get_success_message(self):
        """Get the success message text."""
        return self.find_element(*self.success_alert).text 