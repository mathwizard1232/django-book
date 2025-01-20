from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base_page import BasePage

class BookPage(BasePage):
    def __init__(self, driver):
        super().__init__(driver)
        self.url = '/title/'
        self.title_input = (By.NAME, 'title')
        self.confirm_button = (By.CSS_SELECTOR, 'input[type="submit"]')
        self.success_heading = (By.TAG_NAME, 'h2')
        self.next_author_link = (By.ID, 'next')
        self.success_alert = (By.CLASS_NAME, 'alert-success')
        
        # Add selectors for confirm-book.html page
        self.confirm_without_shelving = (By.CSS_SELECTOR, 'input[value="Confirm Without Shelving"]')
        
        # Add selectors for collection title fields
        self.first_work_title_input = (By.NAME, 'first_work_title')
        self.second_work_title_input = (By.NAME, 'second_work_title')
        self.collection_title_input = (By.NAME, 'title')
        
    def navigate(self):
        """Navigate to the title entry page."""
        self.driver.get(self.driver.current_url.split('#')[0] + self.url)
        
    def wait_for_title_form(self):
        """Wait for the title form to be present."""
        self.wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'basicAutoComplete'))
        )
        
    def enter_title(self, title):
        """Enter a book title."""
        self.wait_for_title_form()
        title_field = self.find_element(*self.title_input)
        title_field.clear()
        title_field.send_keys(title)
        
    def submit_title_form(self):
        """Submit the initial title form to get to the confirmation page."""
        print("\nSubmitting title form")
        confirm = self.find_clickable(*self.confirm_button)
        print(f"Found title submit button: {confirm.get_attribute('value')}")
        confirm.click()
        print("Clicked title submit button")

    def confirm_title(self):
        """Click the final confirmation button."""
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
        
    def verify_next_actions(self, author_name):
        """Verify the next action links are present."""
        next_link = self.find_element(*self.next_author_link)
        assert next_link.text == "Add a book by a different author"
        
        # Find link for same author
        same_author_text = f"Add another book by {author_name}"
        assert self.is_element_present(By.PARTIAL_LINK_TEXT, same_author_text) 
        
    def modify_title_on_confirm(self, new_title):
        """Modify the title on the confirmation page."""
        # Wait for the title input field to be present
        title_input = self.wait.until(
            EC.presence_of_element_located((By.NAME, 'title'))
        )
        title_input.clear()
        title_input.send_keys(new_title) 

    def mark_as_collection(self):
        """Mark the current work as part of a collection."""
        collection_button = self.find_clickable(
            By.CSS_SELECTOR, 
            'button[type="submit"].btn-outline-primary'
        )
        collection_button.click()
        
    def verify_collection_title(self, expected_title):
        """Verify the suggested collection title matches expected."""
        title_input = self.wait.until(
            EC.presence_of_element_located((By.NAME, 'title'))
        )
        actual_title = title_input.get_attribute('value')
        print(f"\nExpected collection title: {expected_title}")
        print(f"Actual collection title: {actual_title}")
        assert actual_title == expected_title

    def confirm_collection(self):
        """Confirm the collection creation."""
        confirm_button = self.find_clickable(
            By.CSS_SELECTOR,
            'input[name="action"][value="Confirm Without Shelving"]'
        )
        confirm_button.click()
        
        # Wait for success alert
        self.wait.until(
            EC.presence_of_element_located(self.success_alert)
        ) 

    def modify_first_work_title(self, new_title):
        """Modify the first work's title on the collection confirmation page."""
        title_input = self.wait.until(
            EC.presence_of_element_located(self.first_work_title_input)
        )
        title_input.clear()
        title_input.send_keys(new_title)
        
    def modify_second_work_title(self, new_title):
        """Modify the second work's title on the collection confirmation page."""
        title_input = self.wait.until(
            EC.presence_of_element_located(self.second_work_title_input)
        )
        title_input.clear()
        title_input.send_keys(new_title) 

    def modify_collection_title(self, new_title):
        """Modify the collection title on the collection confirmation page."""
        title_input = self.wait.until(
            EC.presence_of_element_located(self.collection_title_input)
        )
        title_input.clear()
        title_input.send_keys(new_title) 

    def select_location(self, location_name):
        """Select a location from the dropdown"""
        self.select_dropdown(By.ID, 'location', location_name)
        self.wait_for_ajax()

    def select_room(self, room_name):
        """Select a room from the dropdown"""
        self.select_dropdown(By.ID, 'room', room_name)
        self.wait_for_ajax()

    def select_bookcase(self, bookcase_name):
        """Select a bookcase from the dropdown"""
        self.select_dropdown(By.ID, 'bookcase', bookcase_name)
        self.wait_for_ajax()

    def select_shelf(self, shelf_name):
        """Select a shelf from the dropdown"""
        print(f"\nAttempting to select shelf: {shelf_name}")
        print(f"Current URL: {self.driver.current_url}")
        
        # Wait for shelf dropdown to be present
        try:
            dropdown = self.wait.until(
                EC.presence_of_element_located((By.ID, 'shelf-1'))
            )
            print("Found shelf dropdown")
            
            # Wait for options to be populated (more than just the placeholder)
            def has_options(driver):
                options = dropdown.find_elements(By.TAG_NAME, 'option')
                print(f"Current options: {[opt.text for opt in options]}")
                return len(options) > 1
                
            self.wait.until(has_options)
            print("Shelf options populated")
            
            # Print final options for debugging
            print("Final dropdown options:", 
                  [opt.text for opt in dropdown.find_elements(By.TAG_NAME, 'option')])
        except Exception as e:
            print("Failed to find/wait for shelf dropdown:", str(e))
            print("Available elements with IDs:", [
                elem.get_attribute('id') 
                for elem in self.driver.find_elements(By.CSS_SELECTOR, '[id]')
            ])
            raise
        
        self.select_dropdown(By.ID, 'shelf-1', shelf_name)

    def confirm_shelving(self):
        """Click the confirm and shelve button"""
        # Wait for auto-selection to complete
        self.wait.until(
            EC.element_to_be_clickable(
                (By.ID, 'shelveButton-1')  # Updated selector
            )
        )
        
        confirm = self.find_clickable(By.ID, 'shelveButton-1')  # Updated selector
        print("Found shelving confirm button")
        confirm.click()
        print("Clicked shelving confirm button")