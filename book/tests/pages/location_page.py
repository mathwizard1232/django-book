from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from django.urls import reverse
from .base_page import BasePage
import time

class LocationPage(BasePage):
    """Page object for location management"""
    def __init__(self, browser):
        super().__init__(browser)
        self.url = '/locations/'
        # Locators
        self.location_form = (By.ID, 'locationForm')
        self.entity_type_select = (By.ID, 'id_entity_type')
        self.name_input = (By.ID, 'id_name')
        self.type_select = (By.ID, 'id_type')
        self.shelf_count_input = (By.ID, 'id_shelf_count')
        self.submit_button = (By.ID, 'submit-location')
        self.success_message = (By.CLASS_NAME, 'alert-success')

    def navigate(self):
        """Navigate to the locations page."""
        self.browser.get(self.browser.current_url.split('#')[0] + self.url)
        # Wait for form to be present
        self.wait.until(EC.presence_of_element_located(self.location_form))

    def create_building(self, name, location_type='HOUSE'):
        """Create a new building/location"""
        # Enter name
        self.find_element(*self.name_input).send_keys(name)
        
        # Click submit button
        self.find_element(*self.submit_button).click()
        
        # Wait for page reload after redirect
        self.wait.until(
            EC.presence_of_element_located(self.location_form)
        )

    def create_room(self, name, location):
        """Create a new room in the given location"""
        # Wait for page to reload and form to be present
        self.wait.until(EC.presence_of_element_located(self.location_form))
        
        self.select_dropdown(*self.entity_type_select, 'Room')
        # Wait for room fields to be visible
        self.wait.until(EC.visibility_of_element_located((By.ID, 'room-fields')))
        
        self.find_element(*self.name_input).send_keys(name)
        self.select_dropdown(By.ID, 'id_parent_location', f"{location} (House)")
        self.find_element(*self.submit_button).click()
        
        # Wait for page reload after redirect
        return self.wait.until(EC.presence_of_element_located(self.location_form))

    def create_bookcase(self, name, room_name, shelf_count=5):
        """Create a new bookcase in the given room
        
        Args:
            name: Name for the new bookcase
            room_name: Name of the parent room
            shelf_count: Number of shelves to create (default=5)
        """
        self.select_dropdown(*self.entity_type_select, 'Bookcase')
        # Wait for bookcase fields to be visible
        self.wait.until(EC.visibility_of_element_located((By.ID, 'bookcase-fields')))
        
        self.find_element(*self.name_input).send_keys(name)
        self.find_element(*self.shelf_count_input).send_keys(str(shelf_count))
        
        # Get the room from the database to ensure correct display format
        from book.models import Room
        room = Room.objects.get(name=room_name)
        self.select_dropdown(By.ID, 'id_parent_room', str(room))
        
        self.find_element(*self.submit_button).click()
        
        # Wait for page reload after redirect
        return self.wait.until(EC.presence_of_element_located(self.location_form)) 