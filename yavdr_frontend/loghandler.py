import logging


class LoggingHandler(object):
    def __init__(self, loglevel=logging.INFO):
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.info(f"setting loglevel to {loglevel}")
        self.log.setLevel(loglevel)
        self.log.debug("set Log Level to DEBUG")
