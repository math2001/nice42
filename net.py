import trio
import json
from collections import deque
from logging import getLogger
from constants import *

log = getLogger(__name__)

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
        await self._read_semaphore.acquire()
        log.debug(f"Acquired reading semaphore {self._read_semaphore.value}")
        i = self._read_buf.find(b'\n')
        if i == -1:

            while i == -1:
                try:
                    data = await self._stream.receive_some(BUFSIZE)
                except trio.BrokenResourceError:
                    raise ConnectionClosed("stream closed suddenly while reading")

                log.debug(f"Adding to buffer {data!r}")

                if not data:
                    raise ConnectionClosed("stream closed while reading")
                self._read_buf += data
                i = data.find(b'\n')
            i += len(self._read_buf)

        # we found a line feed!
        string = str(self._read_buf[:i], encoding='utf-8')
        log.debug(f"Read line {string!r}")
        self._read_buf[:i] = []
        self._read_semaphore.release()
        log.debug("Release reading semaphore")
        try:
            return json.loads(string)
        except ValueError:
            log.exception(f"Invalid json: {string!r}")
            raise


    async def write(self, object):
        log.debug("Acquiring writing semaphore")
        await self._write_semaphore.acquire()
        log.debug(f"Sending {object}")
        try:
            await self._stream.send_all(bytes(json.dumps(object) + '\n', encoding='utf-8'))
        except trio.BrokenResourceError:
            raise ConnectionClosed(f"stream closed while writing")
        self._write_semaphore.release()

    async def aclose(self):
        await self._write_semaphore.acquire()
        await self._read_semaphore.acquire()
        await self._stream.aclose()
        self._write_semaphore.release()
        self._read_semaphore.release()


if __name__ == "__main__":
    log.setLevel(10)

    async def handler(stream):
        stream = JSONStream(stream)
        while True:
            print(await stream.read())
    print('running')
    trio.run(trio.serve_tcp, handler, 9043)
