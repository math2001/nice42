import trio
import json
from collections import deque
import logging
from constants import *

log = logging.getLogger(__name__)

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
        log.debug(f"Acquired reading semaphore")
        i = self._read_buf.find(b'\n')
        while i == -1:
            try:
                data = await self._stream.receive_some(BUFSIZE)
            except trio.BrokenResourceError:
                raise ConnectionClosed("stream closed suddenly while reading")

            if not data:
                raise ConnectionClosed("stream closed while reading")

            self._read_buf += data

            i = self._read_buf.find(b'\n')
            log.debug(f"Adding to buffer {data}")

        i += 1

        line = str(self._read_buf[:i], encoding='utf-8')
        self._read_buf[:i] = []
        self._read_semaphore.release()
        log.debug(f"Parsing line: {line!r}")

        if line.strip() == "":
            raise ValueError(f"Invalid empty value: {line!r}")

        try:
            obj = json.loads(line)
        except ValueError:
            log.exception(f"Invalid json: {line!r}")
            raise
        log.debug(f"Returning {obj!r}")
        return obj

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
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(name)-15s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.DEBUG
    )
    log.setLevel(logging.DEBUG)

    async def handler(stream):
        stream = JSONStream(stream)
        while True:
            print(await stream.read())
    log.info("running")
    trio.run(trio.serve_tcp, handler, 9043)
