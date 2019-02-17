import json
from collections import deque
from log import getLogger
from constants import *

log = getLogger()

# TODO: user trio.Semaphore

class ConnectionClosed(Exception):
    pass

_reading_deque = deque()

async def read(stream):
    if len(_reading_deque) == 0:
        # load from actual stream
        data = await stream.receive_some(BUFSIZE)
        log.debug(f"Recieve: {data!r}")

        if not data:
            raise ConnectionClosed(f"stream: {stream}")

        for s in str(data, encoding='utf-8').strip().split('\n'):
            _reading_deque.append(json.loads(s))
    else:
        # make sure that this function is a check point, ie. it doesn't hogg
        # the run loop
        log.debug("Reading from the cache")
        await trio.sleep(0)
    return _reading_deque.popleft()

async def write(stream, object):
    log.debug(f"Sending {object}")
    await stream.send_all(bytes(json.dumps(object) + '\n', encoding='utf-8'))
    