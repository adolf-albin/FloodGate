import os

ADMIN_USERNAME = os.environ.get("FLOODGATE_ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("FLOODGATE_ADMIN_PASSWORD")

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    raise RuntimeError(
        "FLOODGATE_ADMIN_USERNAME and FLOODGATE_ADMIN_PASSWORD "
        "environment variables are required."
    )
