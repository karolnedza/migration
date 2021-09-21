import logging

logging_config = dict(
    version=1,
    formatters={
        'extend': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'simpleTime': {
            'format': '%(asctime)s %(message)s'
        },
        'simple': {
            'format': '%(message)s'
        }
    },
    handlers={
        'consoleHandler': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': logging.WARNING
        },
        'logConsoleHandler': {
            'class': 'logging.FileHandler',
            'formatter': 'simpleTime',
            'level': logging.INFO,
            'filename': 'dm.log',
            'mode': 'a'
        },
        'alertHandler': {
            'class': 'logging.FileHandler',
            'formatter': 'simpleTime',
            'level': logging.WARNING,
            'filename': 'dm.alert.log',
            'mode': 'a'
        }   
    },
    root={
        'handlers': ['consoleHandler'],
        'level': logging.CRITICAL
    },
    loggers={
        'dm': {
            'handlers': ['consoleHandler', 'logConsoleHandler', 'alertHandler'],
            'level': logging.DEBUG,
            'propagate': 0
        }
    }
)
