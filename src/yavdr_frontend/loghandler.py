import logging
from yavdr_frontend.config import LoggingEnum


def create_log_handler(name: str, logLevel: LoggingEnum = LoggingEnum.INFO):
    loghandler = logging.getLogger(name)
    loghandler.setLevel(logLevel)
    return loghandler