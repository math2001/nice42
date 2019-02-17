import trio
import json
from collections import deque
from log import getLogger
from constants import *

log = getLogger()

# TODO: user trio.Semaphore

# idieally, we have more than just a semaphore: it would also need to check
# that it could be writing on 2 different stream "at the same time" without any
# problem. But, in this program, there is only one stream, so it's the exact
# same, with a tiny bit less over head.

class ConnectionClosed(Exception):
    pass

_reading_deque = deque()

read_semaphor = trio.Semaphore(1)

async def read(stream):
    if len(_reading_deque) == 0:
        await read_semaphor.acquire()
        # load from actual stream
        data = await stream.receive_some(BUFSIZE)
        log.debug(f"Recieve: {data!r}")

        if not data:
            raise ConnectionClosed(f"stream: {stream}")

        for s in str(data, encoding='utf-8').strip().split('\n'):
            _reading_deque.append(json.loads(s))
        read_semaphor.release()
    else:
        # make sure that this function is a check point, ie. it doesn't hogg
        # the run loop
        log.debug("Reading from the cache")
        await trio.sleep(0)
    return _reading_deque.popleft()

write_semaphore = trio.Semaphore(1)

async def write(stream, object):
    await write_semaphore.acquire()
    log.debug(f"Sending {object}")
    await stream.send_all(bytes(json.dumps(object) + '\n', encoding='utf-8'))
    write_semaphore.release()
    