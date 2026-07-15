"""Application-wide constants."""

APP_NAME = "EEDP Studio"
APP_VERSION = "0.2"
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"

WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900

STATUS_READY = "Ready"
NO_DEVICE_SELECTED = "No Device Selected"

PROJECT_ROOT_LABEL = "Project"

PROJECT_AREAS = (
    "COMMON",
    "FAN",
    "PRE",
    "CATA",
    "POST",
)

COMMON_SUBNODES = (
    "PLC",
    "MCP",
    "HUB",
)

DEVICE_AREAS = (
    "COMMON",
    "FAN",
    "PRE",
    "CATA",
    "POST",
)

DEVICE_CATEGORIES = (
    "Equipment",
    "Instrument",
)

DEVICE_TYPES = (
    "Pump",
    "Valve",
    "Fan",
    "Pressure Transmitter",
    "Flow Meter",
    "Level Sensor",
    "Thermocouple",
    "RTD",
)
