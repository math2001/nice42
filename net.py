import json
from log import getLogger
from constants import *

log = getLogger()

# TODO: user trio.Semaphore

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
        obj = json.loads(str(data, encoding='utf-8'))
    except ValueError as e:
        return FailParse("could not parse json")
    return obj

async def write(stream, object):
    log.debug(f"Sending {object}")
    await stream.send_all(bytes(json.dumps(object), encoding='utf-8'))
    