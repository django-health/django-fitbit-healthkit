# Functional test of the sample app and fitbit lib.
# Idea is to
# - create an account (see empty dashboard)
# - log out (see login page)
# - log in (see empty dashboard)
# - connect to fitbit (go through fitbit oauth)
# - see the dashboard (with fitbit data!)

import os
import time

import django
from django.conf import settings

# Define the environment variable for Django's settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sample.settings")

# Configure Django for the script
django.setup()

# Use playwright
from django.contrib.auth import get_user_model
from playwright._impl._errors import TimeoutError
from playwright.sync_api import sync_playwright

USERNAME = "testuser"
PASSWORD = "Testpassword123"

# name of the app that is shown in the client's list of connected apps
FITBIT_CLIENT_NAME = os.environ.get("FITBIT_CLIENT_NAME")
# username/password of the fitbit account we want to log in with
FITBIT_USERNAME = os.environ.get("FITBIT_USERNAME")
FITBIT_PASSWORD = os.environ.get("FITBIT_PASSWORD")


def wait_with_dots(seconds, n_dots=80) -> None:
    for _ in range(n_dots):
        print(".", end="", flush=True)
        time.sleep(seconds / n_dots)
    print()  # Move to the next line after the wait is over


def delete_existing_user() -> None:
    User = get_user_model()
    User.objects.filter(username=USERNAME).delete()


def remove_fitbit_connection(connection_expected=False):
    # - login to fitbit
    # - navigate to the settings page on fitbit with "watch" icon top right
    #   direct: https://www.fitbit.com/settings/profile
    # - go to the Applications menu
    #   direct: https://www.fitbit.com/settings/applications
    # if we see one called FITBIT_CLIENT_NAME
    # click the corresponding "Revoke Access" button
    # these applications are li elements in a ul like <li data-test-qa="application-item" ...>
    # the app name is in the child of the li: <span class="column small-12 app-name">...
    # the button is a child of the li as well, and looks like:
    # <div class="column small-12 medium-6 button-container">
    #   <button class="button important" data-open="23992T-revoke-access" aria-controls="23992T-revoke-access" aria-haspopup="true" tabindex="0">
    #     Revoke Access
    #   </button>
    # </div>
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        # page.goto("https://www.fitbit.com/login")

        page.goto("https://www.fitbit.com/settings/applications")
        page.fill("input[type='email']", FITBIT_USERNAME)
        page.fill("input[type='password']", FITBIT_PASSWORD)
        # page.click("button[type='submit']")
        # button has text "Sign in"
        # page.click("button:has-text('Sign in')")
        # await page.getByRole('button', { name: 'Sign In' }).click();
        # in python
        page.click("button:has-text('Sign in')")
        # Check for the FITBIT_CLIENT_NAME app with a timeout of 5 seconds
        app_available = False
        try:
            app_selector = f"li:has-text('{FITBIT_CLIENT_NAME}')"
            page.wait_for_selector(app_selector, timeout=15000)
            print("Found the app, will try to delete it")
            app_available = True
        except TimeoutError:
            print("App not found within 5 seconds.")

        if connection_expected and not app_available:
            raise RuntimeError("Expected to find the app, but it was not found.")

        if app_available:
            # # get the li container here
            # li = page.query_selector(f"li:has-text('{FITBIT_CLIENT_NAME}')")
            # # get the button container
            # button_container = li.query_selector("div.button-container")
            # # click it
            # # button_container.click("button")
            # # TypeError: ElementHandle.click() takes 1 positional argument but 2 were given
            # button_container.click()

            # we also have attribute data-open="[FITBIT_CLIENT_ID]-revoke-access"
            # so we can use that to find the button
            button_selector = (
                f"button[data-open='{settings.FITBIT_CLIENT_ID}-revoke-access']"
            )
            page.click(button_selector)

            print("Revoked access")


def test_fitbit_dashboard():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()
        page.goto("http://localhost:8000")
        # should say "Login to view this page"
        assert page.inner_text("h2") == "Login to view this page"
        # click the login button
        page.click("text=Login")
        # going to need to register
        # click register link
        page.click("text=Register")
        # fill in the form
        page.fill("input[name='username']", USERNAME)
        page.fill("input[name='password1']", PASSWORD)
        page.fill("input[name='password2']", PASSWORD)
        # submit the form
        page.click("button[name='register']")
        # page should say "click to authenticate"
        assert page.inner_text("p") == "Status: click to authenticate"
        # click on that
        page.click("text=Click to authenticate")
        # should be redirected to fitbit login page
        page.fill("input[type='email']", FITBIT_USERNAME)
        page.fill("input[type='password']", FITBIT_PASSWORD)
        page.click("button:has-text('Sign in')")

        try:
            if page.is_visible("text=Allow All"):
                # click on the checkbox with label "Allow All"
                page.check("text=Allow All")
                # click on the "Allow" button
                # id is allow-button, type submit
                page.click("text=Allow")
        except TimeoutError:
            print("Allow All not found. Continuing...")

        # should be redirected to the success page
        # and see "Fitbit successfully connected"
        assert page.inner_text("p") == "Fitbit successfully connected."
        # click on the "Back to dashboard" link
        page.click("text=Back to dashboard")
        # should now see Status: ✅
        assert page.inner_text("p") == "Status: ✅"
        # log out
        page.click("text=Logout")


def reconnect_fitbit():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()
        page.goto("http://localhost:8000")
        # should say "Login to view this page"
        assert page.inner_text("h2") == "Login to view this page"
        # click the login button
        page.click("text=Login")
        # fill in the form
        page.fill("input[name='username']", USERNAME)
        page.fill("input[name='password']", PASSWORD)
        # submit the form
        page.click("button[name='login']")
        # page should say "click to authenticate"
        assert page.inner_text("p") == "Status: ❌ click to re-authenticate"
        # click on that
        page.click("text=Click to re-authenticate")
        # should be redirected to fitbit login page
        page.fill("input[type='email']", FITBIT_USERNAME)
        page.fill("input[type='password']", FITBIT_PASSWORD)
        page.click("button:has-text('Sign in')")
        # click on the checkbox with label "Allow All"
        page.check("text=Allow All")
        # click on the "Allow" button
        # id is allow-button, type submit
        page.click("text=Allow")
        # should be redirected to the success page
        # and see "Fitbit successfully connected"
        assert page.inner_text("p") == "Fitbit successfully connected"
        # click on the "Back to dashboard" link
        page.click("text=Back to dashboard")
        # should now see Status: ✅
        assert page.inner_text("p") == "Status: ✅"
        # log out
        page.click("text=Logout")


if __name__ == "__main__":
    delete_existing_user()
    remove_fitbit_connection()
    wait_with_dots(10)
    test_fitbit_dashboard()
    wait_with_dots(10)
    remove_fitbit_connection(connection_expected=True)
    wait_with_dots(10)
    reconnect_fitbit()
    print("Functional test passed!")
