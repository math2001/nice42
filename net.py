import json
from log import getLogger
from constants import *

log = getLogger()

class ConncetionClosed(Exception):
    pass

class FailParse(Exception):
    pass

async def read(stream):
    data = await stream.receive_some(BUFSIZE)
    log.debug(f"Recieve: {data!r}")
    if not data:
        raise ConncetionClosed(f"stream: {stream}")
    try:
        obj = json.load(stream)
    except ValueError as e:
        return FailParse("could not parse json")
    return obj