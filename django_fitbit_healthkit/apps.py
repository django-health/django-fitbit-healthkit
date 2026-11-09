import logging

from django.apps import AppConfig
from django.core import checks

from . import DEPRECATION_MESSAGE

logger = logging.getLogger(__name__)


def fitbit_api_shutdown_check(app_configs, **kwargs):
    return [
        checks.Warning(
            DEPRECATION_MESSAGE,
            hint="Remove 'django_fitbit_healthkit' from INSTALLED_APPS.",
            id="fitbit.W001",
        )
    ]


class FitbitConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_fitbit_healthkit"
    label = "fitbit"

    def ready(self):
        checks.register(fitbit_api_shutdown_check)
        logger.warning(DEPRECATION_MESSAGE)
