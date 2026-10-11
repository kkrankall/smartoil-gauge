"""Constants for the Smart Oil Gauge integration."""

from datetime import timedelta
import logging

DOMAIN = "smartoil_gauge"
LOGGER = logging.getLogger(__package__)

# The gauge uploads a reading about once an hour.
UPDATE_INTERVAL = timedelta(minutes=30)
