# a simple view that just loads index.html
# and puts the user in the context
import logging
from datetime import date

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from django_fitbit_healthkit.methods import (
    activity_intraday_by_date,
    check_fitbit_access,
    daily_activity_summary,
    sleep_log_by_date,
)

logger = logging.getLogger(__name__)


def index(request: HttpRequest) -> HttpResponse:
    # if the user is logged in, get the daily fitbit data
    context = {"user": request.user}
    if request.user.is_authenticated and hasattr(request.user, "fitbituser"):
        # first let's hit a fitbit api to check if our token is valid
        # to do this, we shouldn't need any specific API scopes
        access = check_fitbit_access(request.user.fitbituser)
        context["connection"] = access
        if access:
            if "activity" in request.user.fitbituser.scopes:
                resp, _ = daily_activity_summary(request.user.fitbituser, date.today())
                context["daily_activity"] = resp.json()

                # intraday is "special"
                # either a personal API token or
                # the app must have been granted this special access from fitbit
                intraday, err = activity_intraday_by_date(
                    request.user.fitbituser, "steps", date.today(), "15min"
                )
                logger.info((intraday, err))
                # if we get a 404 on intraday, it's because we don't have access to that endpoint
                if intraday is None or intraday.status_code == 404:
                    context["activity_intraday"] = "Intraday access not available"
                else:
                    context["activity_intraday"] = intraday.json()

            if "sleep" in request.user.fitbituser.scopes:
                context["sleep_log"] = sleep_log_by_date(
                    request.user.fitbituser, date.today()
                )[0].json()

    return render(request, "sample/index.html", context)


def login_view(request):
    if request.method == "POST":
        print(request.POST)
        form = AuthenticationForm(request, data=request.POST)
        register_form = UserCreationForm(request.POST)
        if "login" in request.POST:
            if form.is_valid():
                auth_login(request, form.get_user())
                return redirect("home")
            else:
                # return to the login page with the errors
                return render(
                    request, "sample/login.html", {"form": form, "errors": form.errors}
                )
        elif "register" in request.POST:
            if register_form.is_valid():
                user = register_form.save()
                auth_login(request, user)
                return redirect("home")
            else:
                # return to the registration page with the errors
                return render(request, "sample/register.html", {"form": register_form})
    else:
        form = AuthenticationForm()
        register_form = UserCreationForm()
    return render(request, "sample/login.html", {"form": form})


def logout_view(request):
    """Log out the user"""
    logout(request)
    return redirect("home")


def register_view(request):
    form = UserCreationForm()
    return render(request, "sample/register.html", {"form": form})
