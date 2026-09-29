# path("login", views.login, name="fitbitlogin"),
# path("success", views.success, name="fitbitsuccess"),
# path("webhook", views.fitbit_subscription, name="fitbitsubscription"),
from urllib.parse import urlparse

from django.test import TestCase
from django.urls import reverse


class MyViewTest(TestCase):
    def test_login(self):
        # Make a request to the view
        response = self.client.get(reverse("fitbitlogin"))

        # can't just do assertRedirects because the URL has query parameters
        # self.assertRedirects(response, 'https://www.fitbit.com/oauth2/authorize', fetch_redirect_response=False)

        # Extract the location header
        full_redirect_url = response["Location"]
        # Parse the URL to extract the scheme and netloc, ignoring query params
        parsed_url = urlparse(full_redirect_url)
        base_redirect_url = (
            f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        )

        # Compare the base URL without query parameters
        self.assertEqual(base_redirect_url, "https://www.fitbit.com/oauth2/authorize")

    def test_success(self):
        pass

    def test_webhook(self):
        pass
