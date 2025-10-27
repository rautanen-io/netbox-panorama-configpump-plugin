"""
Netbox configuration for local development environment
"""

import os
import sys

DEBUG = True
DEVELOPER = True
TEST_MODE = len(sys.argv) > 1 and sys.argv[1] == "test"

ALLOWED_HOSTS = ["*"]
CORS_ORIGIN_ALLOW_ALL = True
CHANGELOG_RETENTION = 7
CSRF_TRUSTED_ORIGINS = ["http://localhost:8000"]
PLUGINS = ["netbox_panorama_configpump_plugin"]

PLUGINS_CONFIG = {
    "netbox_panorama_configpump_plugin": {
        "default_request_timeout": 60,  # seconds
        "default_filename_prefix": "netbox-panorama",
        "ignore_ssl_warnings": True,
        "tokens": {
            "PANO1_TOKEN": os.environ.get("PANO1_TOKEN"),
            "PANO2_TOKEN": os.environ.get("PANO2_TOKEN"),
        },
        "commit_poll_attempts": 30,
        "commit_poll_interval": 3,  # seconds
        "top_level_menu": True,  # How plugin menu is displayed
    }
}

TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
SECRET_KEY = os.environ.get(
    "SECRET_KEY", "12345678901234567890123456789012345678901234567890"
)

DATABASE = {
    "HOST": "postgres",
    "PORT": "",
    "NAME": "netbox",
    "USER": os.environ.get("POSTGRES_USER", "netbox"),
    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
    "CONN_MAX_AGE": 0,
}

REDIS = {
    "tasks": {
        "DATABASE": 0,
        "HOST": os.environ.get("REDIS_HOST", "redis"),
        "PORT": 6379,
        "PASSWORD": os.environ.get("REDIS_PASSWORD", ""),
        "SSL": False,
    },
    "caching": {
        "DATABASE": 1,
        "HOST": os.environ.get("REDIS_HOST", "redis"),
        "PORT": 6379,
        "PASSWORD": os.environ.get("REDIS_PASSWORD", ""),
        "SSL": False,
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "CRITICAL" if TEST_MODE else None,
            "stream": sys.stdout,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}
