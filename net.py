import trio
import json
from collections import deque
from log import getLogger
from constants import *

log = getLogger()

class ConnectionClosed(Exception):
    pass

class JSONStream:
    """ A wrapper around a trio.Stream """

    def __init__(self, stream):
        self.stream = stream
        self._reading_deque = deque()
        self._read_semaphore = trio.Semaphore(1)
        self._write_semaphore = trio.Semaphore(1)

    async def read(self):
        if len(self._reading_deque) == 0:
            log.debug("Acquiring writing semaphore")
            await self._read_semaphore.acquire()
            log.debug("Reading...")

            try:
                data = await self.stream.receive_some(BUFSIZE)
            except trio.BrokenResourceError:
                raise ConnectionClosed(f"reading from {self.stream}")
            log.debug(f"Receive: {data!r}")
            self._read_semaphore.release()

            if not data:
                raise ConnectionClosed(f"reading from {self.stream}")

            for s in str(data, encoding='utf-8').strip().split('\n'):
                self._reading_deque.append(json.loads(s))
        else:
            # make sure that this function is a check point, ie. it doesn't hogg
            # the run loop
            log.debug("Reading from the cache")
            await trio.sleep(0)
        return self._reading_deque.popleft()

    async def write(self, object):
        log.debug("Acquiring writing semaphore")
        await self._write_semaphore.acquire()
        log.debug(f"Sending {object}")
        try:
            await self.stream.send_all(bytes(json.dumps(object) + '\n', encoding='utf-8'))
        except trio.BrokenResourceError:
            raise ConnectionClosed(f"writing on {self.stream}")
        self._write_semaphore.release()