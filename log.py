import sys

log = None

def getLogger():
    if log:
        return log

    logger = logging.getLogger()
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    log = logger
    return log
