import json
import urllib
from datetime import date

import requests
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from .models import FitbitNotification, FitbitUser
from .util import encoded_secret, verify_fitbit_signature


def login(request: HttpRequest) -> HttpResponseRedirect:
    """
    Redirect to authenticate to with Fitbit.
    """
    current_site = get_current_site(request)
    base_url = "http://" + current_site.domain
    data = {
        "client_id": settings.FITBIT_CLIENT_ID,
        "redirect_uri": base_url + reverse("fitbitsuccess"),
        "response_type": "code",
        "scope": settings.FITBIT_SCOPES,
        "expires_in": 604800,
    }
    return HttpResponseRedirect(
        settings.FITBIT_AUTHORIZATION_URI + "?" + urllib.parse.urlencode(data)
    )


def success(request: HttpRequest) -> HttpResponse:
    if "code" not in request.GET:
        return Http404(f"No access code returned: {request.GET}.")

    current_site = get_current_site(request)
    base_url = "http://" + current_site.domain

    data = {
        # maybe an error, but the docs here say client_id:
        # https://dev.fitbit.com/build/reference/web-api/oauth2/
        # though, above it doesn't say it's required
        # but the tool uses clientId:
        # https://dev.fitbit.com/apps/oauthinteractivetutorial
        "client_id": settings.FITBIT_CLIENT_ID,
        "code": request.GET["code"],
        "grant_type": "authorization_code",
        "redirect_uri": base_url + reverse("fitbitsuccess"),
    }
    headers = {
        "Authorization": f"Basic {encoded_secret(settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)}"
    }
    r = requests.post(
        settings.FITBIT_ACCESS_REFRESH_TOKEN_REQUEST_URI, data=data, headers=headers
    )
    # rather than raise an application error, pass that error back to the user:
    # r.raise_for_status()
    if r.status_code != requests.codes.ok:
        raise Http404(f"Error in fitbit oauth handshake: {r.text}")

    fitbit_user = r.json()
    if "access_token" not in fitbit_user:
        raise Http404(f"No access token returned response: {fitbit_user}.")

    if settings.DEBUG:
        print(fitbit_user)

    # update the token too
    fb_user, created = FitbitUser.objects.get_or_create(
        user=request.user,
        defaults={
            "access_token": fitbit_user.get("access_token"),
            "refresh_token": fitbit_user.get("refresh_token"),
            "expires_in": fitbit_user.get("expires_in"),
            "fitbit_id": fitbit_user.get("user_id"),
            "scopes": fitbit_user.get("scope"),
        },
    )

    if not created:
        # Update the token attributes
        fb_user.access_token = fitbit_user.get("access_token")
        fb_user.refresh_token = fitbit_user.get("refresh_token")
        fb_user.expires_in = fitbit_user.get("expires_in")
        fb_user.fitbit_id = fitbit_user.get("user_id")
        fb_user.scopes = fitbit_user.get("scope")
        fb_user.save()

    # get_athlete_activities(ath, max_requests=1)
    # t = threading.Thread(target=get_user_data, args=[s, 100])
    # t.setDaemon(True)
    # t.start()

    redir_uri = (
        settings.FITBIT_SUCCESS_TEMPLATE
        if hasattr(settings, "FITBIT_SUCCESS_TEMPLATE")
        else "fitbit/success.html"
    )
    return render(request, redir_uri, fitbit_user)


def fitbit_subscription(request: HttpRequest) -> HttpResponse:
    """
    Fitbit sends a subscription notification to this endpoint.

    As of yet, we still need to:
    - Create subscriptions for users we want them on
    - Handle the notifications (go get the data)
    """
    if request.method == "GET":
        verify = request.GET.get("verify")
        if verify == settings.FITBIT_SUBSCRIPTION_VERIFICATION_CODE:
            return HttpResponse(status=204)
        return HttpResponse(status=404)

    # we have a post request
    # check signature
    fitbit_signature = request.headers.get("x-fitbit-signature")
    if not verify_fitbit_signature(fitbit_signature, request.body):
        return HttpResponse(status=404)

    # save the notifications
    # we get up to 100 at a time so use a bulk load
    data = json.loads(request.body)
    objs = [
        FitbitNotification(
            user=FitbitUser.objects.get(fitbit_id=d["ownerId"]),
            notification=d["collectionType"],
            date=date.fromisoformat(d["date"]),
        )
        for d in data
    ]
    FitbitNotification.objects.bulk_create(objs)
    return HttpResponse(status=204)
