import warnings

DEPRECATION_MESSAGE = (
    "django-fitbit-healthkit is ARCHIVED and NO LONGER WORKS: the Fitbit Web API "
    "stopped serving requests in November 2026. Every API call made by this package "
    "will fail. This is the final release; there will be no further updates or "
    "security fixes. Migrate to django-google-health "
    "(https://github.com/django-health/django-google-health)."
)

warnings.warn(DEPRECATION_MESSAGE, FutureWarning, stacklevel=2)
