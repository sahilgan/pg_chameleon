import json


def make_logback_config(formatter_dict, logger_dict, handler_dict, f_path, logger_name):
    megadict = {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "cham_formatter": formatter_dict
        },
        "handlers": {
            "charm_log_handler": handler_dict
        },
        "loggers": { logger_name: logger_dict }
    }
    with open(f_path, 'w') as f:
        json.dump(megadict, f, indent=4)
