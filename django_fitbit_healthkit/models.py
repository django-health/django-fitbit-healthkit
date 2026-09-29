import logging
from ast import Dict
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.db import models

from .util import encoded_secret

logger = logging.getLogger(__name__)


class FitbitUser(models.Model):
    """Adds a token to a custom User model."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    fitbit_id = models.CharField(max_length=1024)
    access_token = models.CharField(max_length=1024)
    refresh_token = models.CharField(max_length=1024)
    expires_in = models.IntegerField()
    scopes = models.CharField(max_length=1024)
    # store the last updated datetime
    # so that we can check if the token is expired
    last_updated = models.DateTimeField(auto_now=True)

    @property
    def is_expired(self) -> bool:
        return self.expires_in is None or datetime.now(timezone.utc) > (
            self.last_updated + timedelta(seconds=self.expires_in)
        )

    def get_new_tokens(self) -> tuple[Dict | None, Exception | None]:
        logger.info("Getting new tokens")
        if self.refresh_token is None or self.refresh_token == "":
            logger.info("No refresh token, can't get new tokens")
            return (None, Exception("No refresh token available"))

        params = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_secret(settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)}",
        }
        try:
            response = requests.post(
                settings.FITBIT_ACCESS_REFRESH_TOKEN_REQUEST_URI,
                headers=headers,
                params=params,
            )
            if response.status_code == 401:
                logger.info("401 from fitbit, unauthorized")
                # unauthorized, clear the tokens
                return (None, Exception("Unauthorized"))
            elif response.status_code == 200:
                # return the new token data
                return (response.json(), None)
            else:
                # should propogate the error up to the caller
                logger.info(f"Error in fitbit oauth handshake: {response.text}")
                return (
                    None,
                    Exception(f"Error in fitbit oauth handshake: {response.text}"),
                )
        # catch these separately
        except requests.exceptions.RequestException as e:
            logger.info(f"Error in fitbit token request: {e}")
            return (None, e)
        except Exception as e:
            logger.info(f"Error in fitbit token request: {e}")
            return (None, e)

    def update_tokens(self) -> None:
        """
        Updates the tokens.
        Raises a generic exception if there are any errors.
        """
        logger.info("Updating tokens")
        required_keys = ["access_token", "refresh_token", "expires_in"]
        reauth_data, err = self.get_new_tokens()
        if err is not None:
            logger.info((reauth_data, err))
            raise Exception(f"Error in fitbit oauth handshake: {err}")
        elif reauth_data is None or any(x not in reauth_data for x in required_keys):
            raise Exception(f"Missing keys in returned response: {reauth_data}")
        # update the user credentials with the new token
        self.access_token = reauth_data["access_token"]
        self.refresh_token = reauth_data["refresh_token"]
        self.expires_in = reauth_data["expires_in"]
        self.scopes = reauth_data.get("scope", "")
        self.save()
        logger.info("Successfully updated tokens")

    def make_request(
        self,
        request_type: str,
        *args,
        headers: Dict | None = {},
        max_fetch_attempts: int = 3,
        **kwargs,
    ) -> tuple[requests.models.Response | None, Exception | None]:
        """
        Wrapper for requests.get and requests.post that will handle
        the token refresh and retries for the user credentials.

        This captures all exceptions and returns them as the second
        tuple element.
        """
        if self.is_expired:
            logger.info("Token expired, will attempt an update")
            try:
                self.update_tokens()
            except Exception as e:
                return (None, e)

        fetch_attempts = 0

        headers = {"authorization": f"Bearer {self.access_token}", **headers}

        while fetch_attempts < max_fetch_attempts:
            logger.info(f"Fetch attempt #{fetch_attempts}")
            fetch_attempts += 1
            if request_type == "GET":
                requester = requests.get
            else:
                requester = requests.post

            try:
                response = requester(*args, headers=headers, **kwargs)
            except requests.exceptions.RequestException as e:
                return (None, e)
            logger.info((response.status_code, response.text))

            if response.status_code == 401:
                try:
                    self.update_tokens()
                except Exception as e:
                    return (None, e)
                headers["authorization"] = f"Bearer {self.access_token}"
                # make another fetch attempt
                continue
            elif response.status_code == 200:
                return (response, None)
            elif response.status_code == 429:
                # backoff warning/error
                # don't keep making requests
                # should propogate the error up to the caller
                return (None, Exception(f"Backoff: {response.text}"))
            # else, we'll just try again up to max_fetch_attempts
        return (None, Exception("Max attempts"))


class FitbitNotification(models.Model):
    """
    Stores a notification from Fitbit.

    We'll get POSTs from Fitbit to our subscription endpoint with the following format:

    [
        {
            "collectionType": "foods",
            "date": "2010-03-01",
            "ownerId": "USER_1",
            "ownerType": "user",
            "subscriptionId": "1234"
        },
        {
            "collectionType": "foods",
            "date": "2010-03-02",
            "ownerId": "USER_1",
            "ownerType": "user",
            "subscriptionId": "1234"
        },
        {
            "collectionType": "activities",
            "date": "2010-03-01",
            "ownerId": "X1Y2Z3",
            "ownerType": "user",
            "subscriptionId": "2345"
        }
    ]
    """

    user = models.ForeignKey(FitbitUser, on_delete=models.CASCADE)
    date = models.DateField()
    notification = models.TextField()
    added = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user}: {self.date} - {self.notification}"
