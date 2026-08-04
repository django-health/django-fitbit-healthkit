import logging
from datetime import date

import requests

from .models import FitbitError, FitbitUser

logger = logging.getLogger(__name__)


def check_fitbit_access_profile(fitbitUser: FitbitUser) -> bool:
    """
    This is a good idea BUT need write access to profile do use this endpoint.
    > Invalid authentication token. The PROFILE (WRITE) scope is required.
    """
    resp, _ = fitbitUser.make_request(
        "get", "https://api.fitbit.com/1/user/-/profile.json"
    )

    if resp.status_code != 200:
        return False

    # if this succeeded, update their scopes from the profile
    new_scopes = resp.json()["user"]["scope"]
    # check if they're difference
    if new_scopes != fitbitUser.scopes:
        fitbitUser.scopes = new_scopes
        fitbitUser.save()
    return True


# instead, wrap fitbitUser.update_tokens()
# and catch exceptions to return T/F on having access
def check_fitbit_access(fitbitUser: FitbitUser) -> bool:
    try:
        fitbitUser.update_tokens()
    except FitbitError as e:
        logger.info(f"Error wrapped in check_fitbit_access: {e}")
        return False
    return True


def daily_activity_summary(
    fitbitUser: FitbitUser, d: date
) -> tuple[requests.models.Response | None, Exception | None]:
    """
    ref: https://dev.fitbit.com/build/reference/web-api/activity/get-daily-activity-summary/
    format: /1/user/[user-id]/activities/date/[date].json
    """
    return fitbitUser.make_request(
        "get",
        f"https://api.fitbit.com/1/user/-/activities/date/{d.isoformat()}.json",
    )


def sleep_log_by_date(
    fitbitUser: FitbitUser, d: date
) -> tuple[requests.models.Response | None, Exception | None]:
    """
    ref: https://dev.fitbit.com/build/reference/web-api/sleep/get-sleep-log-by-date/
    format: /1.2/user/[user-id]/sleep/date/[date].json
    """
    return fitbitUser.make_request(
        "get", f"https://api.fitbit.com/1.2/user/-/sleep/date/{d.isoformat()}.json"
    )


def sleep_log_by_date_range(
    fitbitUser: FitbitUser, start_date: date, end_date: date
) -> tuple[requests.models.Response | None, Exception | None]:
    """
    ref: https://dev.fitbit.com/build/reference/web-api/sleep/get-sleep-log-by-date-range/
    format: /1.2/user/[user-id]/sleep/date/[startDate]/[endDate].json

    note maximum range: 100 days
    """
    # check max range
    if (end_date - start_date).days > 100:
        logger.info("Date range is too long, won't try to fetch data.")
        return {}
    return fitbitUser.make_request(
        "get",
        f"https://api.fitbit.com/1.2/user/-/sleep/date/{start_date.isoformat()}/{end_date.isoformat()}.json",
    )


def activity_intraday_by_date(
    fitbitUser: FitbitUser, activity: str, d: date, interval: str
) -> tuple[requests.models.Response | None, Exception | None]:
    """
    ref: https://dev.fitbit.com/build/reference/web-api/intraday/get-activity-intraday-by-date/
    format:
    * /1/user/[user-id]/activities/[resource]/date/[date]/1d/[detail-level].json
    * /1/user/[user-id]/activities/[resource]/date/[date]/1d/[detail-level]/time/[start-time]/[end-time].json
    """
    # calories | distance | elevation | floors | steps
    if activity not in ["calories", "distance", "elevation", "floors", "steps"]:
        logger.info(f"Invalid activity {activity}, won't try to fetch data.")
        return {}
    # 1min | 5min | 15min
    if interval not in ["1min", "5min", "15min"]:
        logger.info(f"Invalid interval {interval}, won't try to fetch data.")
        return {}

    return fitbitUser.make_request(
        "get",
        f"https://api.fitbit.com/1/user/-/activities/{activity}/date/{d.isoformat()}/1d/{interval}.json",
    )


def activity_timeseries_by_date(
    fitbitUser: FitbitUser, resource: str, d: date, period: str
) -> tuple[requests.models.Response | None, Exception | None]:
    """
    ref: https://dev.fitbit.com/build/reference/web-api/activity-timeseries/get-activity-timeseries-by-date/
    format: /1/user/[user-id]/activities/[resource-path]/date/[date]/[period].json
    """
    all_activity_resources = [
        "activityCalories",
        "calories",
        "caloriesBMR",
        "distance",
        "elevation",
        "floors",
        "minutesSedentary",
        "minutesLightlyActive",
        "minutesFairlyActive",
        "minutesVeryActive",
        "steps",
    ]
    tracker_only_resources = [
        "tracker/activityCalories",
        "tracker/calories",
        "tracker/distance",
        "tracker/elevation",
        "tracker/floors",
        "tracker/minutesSedentary",
        "tracker/minutesLightlyActive",
        "tracker/minutesFairlyActive",
        "tracker/minutesVeryActive",
        "tracker/steps",
    ]
    if resource not in all_activity_resources + tracker_only_resources:
        logger.info(f"Invalid resource {resource}, won't try to fetch data.")
        return {}
    if period not in ["1d", "7d", "30d", "1w", "1m", "3m", "6m", "1y"]:
        logger.info(f"Invalid period {period}, won't try to fetch data.")
        return {}
    return fitbitUser.make_request(
        "get",
        f"https://api.fitbit.com/1/user/-/activities/{resource}/date/{d.isoformat()}/{period}.json",
    )


def activity_timeseries_by_date_range(
    fitbitUser: FitbitUser, resource: str, start_date: date, end_date: date
) -> tuple[requests.models.Response | None, Exception | None]:
    """
    ref: https://dev.fitbit.com/build/reference/web-api/activity-timeseries/get-activity-timeseries-by-date-range/
    format: /1/user/[user-id]/activities/[resource-path]/date/[start-date]/[end-date].json

    note maximum range: 30 days for calories, 1095 days for everything else
    """
    # check max range
    if (
        resource in {"activityCalories", "tracker/activityCalories"}
        and (end_date - start_date).days > 30
    ) or (end_date - start_date).days > 1095:
        logger.info("Date range is too long, won't try to fetch data.")
        return {}
    all_activity_resources = [
        "activityCalories",
        "calories",
        "caloriesBMR",
        "distance",
        "elevation",
        "floors",
        "minutesSedentary",
        "minutesLightlyActive",
        "minutesFairlyActive",
        "minutesVeryActive",
        "steps",
    ]
    tracker_only_resources = [
        "tracker/activityCalories",
        "tracker/calories",
        "tracker/distance",
        "tracker/elevation",
        "tracker/floors",
        "tracker/minutesSedentary",
        "tracker/minutesLightlyActive",
        "tracker/minutesFairlyActive",
        "tracker/minutesVeryActive",
        "tracker/steps",
    ]
    if resource not in all_activity_resources + tracker_only_resources:
        logger.info(f"Invalid resource {resource}, won't try to fetch data.")
        return {}
    return fitbitUser.make_request(
        "get",
        f"https://api.fitbit.com/1/user/-/activities/{resource}/date/{start_date.isoformat()}/{end_date.isoformat()}.json",
    )
