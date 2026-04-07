# evalify_app/tests_selenium.py
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

class SeleniumTests(StaticLiveServerTestCase):
    """Test suite using Selenium to verify frontend pages."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        service = Service(ChromeDriverManager().install())
        cls.driver = webdriver.Chrome(service=service)
        cls.driver.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def test_home_page_loads(self):
        """Verify home page loads with correct title."""
        self.driver.get(self.live_server_url + '/')
        self.assertIn('Evalify - Smart Assessment Platform', self.driver.title)

    def test_signup_page_loads(self):
        """Verify signup page loads correctly."""
        self.driver.get(self.live_server_url + '/signup/')
        self.assertEqual(self.driver.title, 'Evalify - Create Account')
        # Check presence of key elements
        self.assertTrue(self.driver.find_element(By.CSS_SELECTOR, 'input[placeholder*="profile name"]').is_displayed())
        self.assertTrue(self.driver.find_element(By.CSS_SELECTOR, 'input[placeholder*="email"]').is_displayed())

    def test_signin_page_loads(self):
        """Verify signin page loads correctly."""
        self.driver.get(self.live_server_url + '/signin/')
        self.assertEqual(self.driver.title, 'Evalify - Sign In')
        # Check heading
        heading = self.driver.find_element(By.TAG_NAME, 'h2')
        self.assertIn('Sign In To Continue', heading.text)

    def test_navigation_from_home(self):
        """Test that buttons on home page lead to correct auth pages."""
        self.driver.get(self.live_server_url + '/')

        # Click SIGN UP button (button with class 'btn-signup')
        signup_btn = self.driver.find_element(By.CSS_SELECTOR, '.btn-signup')
        signup_btn.click()
        self.assertIn('/signup/', self.driver.current_url)
        self.assertEqual(self.driver.title, 'Evalify - Create Account')

        # Go back to home
        self.driver.back()

        # Click SIGN IN button (button with class 'btn-signin')
        signin_btn = self.driver.find_element(By.CSS_SELECTOR, '.btn-signin')
        signin_btn.click()
        self.assertIn('/signin/', self.driver.current_url)
        self.assertEqual(self.driver.title, 'Evalify - Sign In')

    def test_navigation_between_auth_pages(self):
        """Test links between signup and signin pages work."""
        # From signup page, go to signin
        self.driver.get(self.live_server_url + '/signup/')
        login_link = self.driver.find_element(By.CSS_SELECTOR, '.login-link a')
        login_link.click()
        self.assertIn('/signin/', self.driver.current_url)

        # From signin page, go back to signup
        signup_link = self.driver.find_element(By.CSS_SELECTOR, '.login-link a')
        signup_link.click()
        self.assertIn('/signup/', self.driver.current_url)
        
    class FacultyCourseManagementTests(StaticLiveServerTestCase):
    """Selenium tests for faculty course management (add course, CLO, PLO, student)"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        service = Service(ChromeDriverManager().install())
        cls.driver = webdriver.Chrome(service=service)
        cls.driver.implicitly_wait(10)
        cls.driver.maximize_window()

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def login_as_faculty(self):
        """Helper method to log in as a faculty user before each test."""
        # You need to implement actual login flow based on your auth system
        # For now, assuming a test faculty user exists and using a simple login page.
        # Adjust selectors to match your login page.
        self.driver.get(self.live_server_url + '/signin/')
        self.driver.find_element(By.NAME, 'email').send_keys('faculty@example.com')
        self.driver.find_element(By.NAME, 'password').send_keys('testpass123')
        self.driver.find_element(By.CSS_SELECTOR, '.submit-btn').click()
        # Wait for redirect to faculty dashboard
        WebDriverWait(self.driver, 5).until(
            EC.url_contains('/faculty/')
        )

    def test_add_course(self):
        """Test adding a new course via modal."""
        # First, login and go to courses page
        self.login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/courses/')

        # Click "Add Course" button
        add_btn = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.btn-primary:contains("Add Course")'))
        )
        # Since :contains is not native, use XPath
        add_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'Add Course')]")
        add_btn.click()

        # Wait for modal to appear
        modal = WebDriverWait(self.driver, 5).until(
            EC.visibility_of_element_located((By.ID, 'addCourseModal'))
        )
        # Fill in course details
        self.driver.find_element(By.ID, 'cCode').send_keys('CSE-999')
        self.driver.find_element(By.ID, 'cName').send_keys('Selenium Test Course')
        self.driver.find_element(By.ID, 'cDesc').send_keys('Course created by Selenium test')
        self.driver.find_element(By.ID, 'cSemester').send_keys('Fall 2025')
        self.driver.find_element(By.ID, 'cCredits').clear()
        self.driver.find_element(By.ID, 'cCredits').send_keys('4')

        # Submit form
        self.driver.find_element(By.CSS_SELECTOR, '#addCourseModal .btn-full').click()

        # After submission, page should reload and show success message or new course
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Course created')]"))
        )
        # Verify new course appears in list
        course_elem = self.driver.find_element(By.XPATH, "//div[contains(text(),'CSE-999: Selenium Test Course')]")
        self.assertTrue(course_elem.is_displayed())

    def test_add_plo(self):
        """Test adding a PLO from the CLO modal."""
        self.login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/courses/')

        # Ensure at least one course exists; if not, create one first.
        # For simplicity, assume there is a course. Then expand the first accordion.
        first_accordion = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '.accordion-trigger'))
        )
        first_accordion.click()
        time.sleep(0.5)

        # Click "Add CLO" button (inside the CLO tab, but tab may be active)
        add_clo_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add CLO')]")
        add_clo_btn.click()

        # Wait for add CLO modal
        modal = WebDriverWait(self.driver, 5).until(
            EC.visibility_of_element_located((By.ID, 'addCloModal'))
        )

        # Scroll to quick PLO section and add a new PLO
        quick_desc = self.driver.find_element(By.ID, 'quickPloDesc')
        quick_desc.send_keys('Test PLO from Selenium')
        add_plo_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'+ Add PLO')]")
        add_plo_btn.click()

        # Wait for success message
        success_msg = WebDriverWait(self.driver, 5).until(
            EC.visibility_of_element_located((By.ID, 'ploAddedMsg'))
        )
        self.assertEqual(success_msg.text, '✓ PLO added!')

        # Now fill CLO description and submit
        self.driver.find_element(By.ID, 'cloDesc').send_keys('Test CLO from Selenium')
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, '#addCloModal .btn-full')
        submit_btn.click()

        # After submit, page should reload and show new CLO
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Test CLO from Selenium')]"))
        )
        # Also verify the new PLO appears in the PLO list (via tag)
        plo_tag = self.driver.find_element(By.XPATH, "//span[contains(text(),'PLO') and contains(text(),'Test PLO')]")
        self.assertTrue(plo_tag.is_displayed())

    def test_add_student_to_course(self):
        """Test adding a student to a course."""
        self.login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/courses/')

        # Expand first course accordion
        first_accordion = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '.accordion-trigger'))
        )
        first_accordion.click()
        time.sleep(0.5)

        # Click on "Students" tab
        students_tab = self.driver.find_element(By.CSS_SELECTOR, '.tab-btn[data-tab^="students_"]')
        students_tab.click()
        time.sleep(0.5)

        # Click "+ Add Student" button
        add_student_btn = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'+ Add Student')]"))
        )
        add_student_btn.click()

        # Wait for modal
        modal = WebDriverWait(self.driver, 5).until(
            EC.visibility_of_element_located((By.ID, 'addStudentModal'))
        )
        # Fill email (assume a test student exists with this email)
        self.driver.find_element(By.ID, 'studentEmail').send_keys('student@example.com')
        submit = self.driver.find_element(By.CSS_SELECTOR, '#addStudentModal .btn-full')
        submit.click()

        # Wait for success message in modal
        msg = WebDriverWait(self.driver, 5).until(
            EC.visibility_of_element_located((By.ID, 'studentMsg'))
        )
        self.assertIn('added successfully', msg.text)
        # After auto-reload, the student should appear in the list
        time.sleep(2)  # Wait for reload
        student_name = self.driver.find_element(By.XPATH, "//div[contains(text(),'student@example.com')]")
        self.assertTrue(student_name.is_displayed())

    def test_tab_switching(self):
        """Test that tabs (CLOs, PLOs, Students) switch content correctly."""
        self.login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/courses/')

        # Expand first accordion
        first_accordion = self.driver.find_element(By.CSS_SELECTOR, '.accordion-trigger')
        first_accordion.click()
        time.sleep(0.5)

        # Get all tab buttons
        tabs = self.driver.find_elements(By.CSS_SELECTOR, '.tab-bar .tab-btn')
        self.assertGreaterEqual(len(tabs), 3)

        # Tab 0: CLOs - should be active by default
        self.assertTrue('active' in tabs[0].get_attribute('class'))
        clo_content = self.driver.find_element(By.CSS_SELECTOR, '.tab-content.active')
        self.assertIsNotNone(clo_content)

        # Click PLO tab
        tabs[1].click()
        time.sleep(0.5)
        self.assertTrue('active' in tabs[1].get_attribute('class'))
        plo_content = self.driver.find_element(By.CSS_SELECTOR, '.tab-content.active')
        self.assertNotEqual(clo_content, plo_content)

        # Click Students tab
        tabs[2].click()
        time.sleep(0.5)
        self.assertTrue('active' in tabs[2].get_attribute('class'))
        students_content = self.driver.find_element(By.CSS_SELECTOR, '.tab-content.active')
        self.assertNotEqual(plo_content, students_content)

    def test_accordion_expand_collapse(self):
        """Test that accordion items expand/collapse when clicked."""
        self.login_as_faculty()
        self.driver.get(self.live_server_url + '/faculty/courses/')

        # Find first accordion trigger
        trigger = self.driver.find_element(By.CSS_SELECTOR, '.accordion-trigger')
        body = self.driver.find_element(By.CSS_SELECTOR, '.accordion-body')
        # Initially, body should be hidden (display: none)
        self.assertFalse(body.is_displayed())

        trigger.click()
        time.sleep(0.5)
        self.assertTrue(body.is_displayed())

        trigger.click()
        time.sleep(0.5)
        self.assertFalse(body.is_displayed())