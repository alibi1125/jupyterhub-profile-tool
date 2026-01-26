import os
import logging
import logging.config

def setup_logging(debug: bool):
    level = "DEBUG" if debug else "INFO"

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(levelname)s %(name)s: %(message)s"
            }
        },
        "handlers": {
            "journal": {
                "class": "systemd.journal.JournalHandler",
                "formatter": "default",
                "level": level,
                "SYSLOG_IDENTIFIER": "jupyterhub_profile_tool"
            }
        },
        "root": {
            "level": level,
            "handlers": ["journal"]
        }
    }

    logging.config.dictConfig(LOGGING_CONFIG)

def main():
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)
    setup_logging(debug=True)

    from .profilemaker import ProfileMaker
    ProfileMaker.launch_instance()

if __name__ == "__main__":
    main()
