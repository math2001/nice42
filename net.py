import trio
import json
from collections import deque
from log import getLogger
from constants import *

log = getLogger()

# TODO: test that! it should be easy and fun with trio

class ConnectionClosed(Exception):
    pass

class JSONStream:
    """ A wrapper around a trio.Stream """

    def __init__(self, stream):
        self._stream = stream

        self._write_semaphore = trio.Semaphore(1)

        # blocks reading from stream and _read_buf at the same time
        self._read_semaphore = trio.Semaphore(1)

        self._read_buf = bytearray()

    async def read(self):
        i = self._read_buf.find(b'\n')
        if i == -1:
            log.debug("Aquire reading semaphore")
            await self._read_semaphore.acquire()

            while i == -1:
                data = await self._stream.receive_some(BUFSIZE)
                log.debug(f"Adding to buffer {data!r}")
                if not data:
                    raise ConnectionClosed("stream closed")
                self._read_buf += data
                i = data.find(b'\n')
            i += len(self._read_buf)

        # we found a line feed!
        string = str(self._read_buf[:i], encoding='utf-8')
        log.debug(f"Read line {string!r}")
        self._read_buf[:i] = []
        self._read_semaphore.release()
        log.debug("Release reading semaphore")
        return json.loads(string)


    async def write(self, object):
        log.debug("Acquiring writing semaphore")
        await self._write_semaphore.acquire()
        log.debug(f"Sending {object}")
        try:
            await self._stream.send_all(bytes(json.dumps(object) + '\n', encoding='utf-8'))
        except trio.BrokenResourceError:
            raise ConnectionClosed(f"writing on {self._stream}")
        self._write_semaphore.release()

    async def aclose(self):
        await self._write_semaphore.acquire()
        await self._read_semaphore.acquire()
        await self._stream.aclose()
        self._write_semaphore.release()
        self._read_semaphore.release()