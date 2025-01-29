import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

@pytest.fixture(scope="session")
def driver():
    """Create a Selenium WebDriver instance."""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode for CI
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(0.5)  # Reduce from 10 seconds to 0.5 seconds
    yield driver
    driver.quit()

@pytest.fixture
def live_server_url(live_server):
    """Get the live server URL."""
    return live_server.url

@pytest.fixture
def browser(driver, live_server_url):
    """Configure the browser with base URL."""
    driver.get(live_server_url)
    return driver 