import trio
import json
import time
from collections import deque
import logging
from constants import *

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


# the key used to store timestamps to invalidate packets
# this could be a per-instance constant, but it will be much easier if
# everything uses the same key
TIME_KEY = 't'

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
        log.debug(f"(release read semaphore) Parsing line: {line!r}")

        if line.strip() == "":
            raise ValueError(f"Invalid empty value: {line!r}")

        try:
            obj = json.loads(line)
        except ValueError:
            log.exception(f"Invalid JSON: {line!r}")
            raise

        if not isinstance(obj, dict):
            raise ValueError(f"should be dict, got {type(obj)} in {obj}")


        log.debug(f"Returning {obj!r}")
        return obj

    async def write(self, obj):
        log.debug("Acquiring writing semaphore")
        if not isinstance(obj, dict):
            raise ValueError(f"should send dict, got {obj!r}")

        await self._write_semaphore.acquire()
        log.debug(f"Sending {obj}")
        try:
            await self._stream.send_all(bytes(json.dumps(obj) + '\n', encoding='utf-8'))
        except trio.BrokenResourceError:
            raise ConnectionClosed(f"stream closed while writing")

        self._write_semaphore.release()
        log.debug("Release writing semaphore")

    async def aclose(self):
        await self._write_semaphore.acquire()
        await self._read_semaphore.acquire()
        await self._stream.aclose()
        self._write_semaphore.release()
        self._read_semaphore.release()

class TimedStream(JSONStream):

    """ Time aware JSON stream. It discards old messages. Good any stream based
    on UDP. If you use TCP, it's very unlikely that you want to use this class.
    Instead, just use a regular JSONStream.

    I agree this is a very bad name, but I don't have any better ideas right
    now...
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_timestamp = 0

    async def read(self):
        obj = await super().read()

        if TIME_KEY not in obj:
            raise ValueError(f"no time key ({TIME_KEY!r}) in {obj!r}")

        if obj[TIME_KEY] < self._last_timestamp:
            log.warning(f"Discarding old message (t={self._last_timestamp}) {obj}")
            return await self.read()

        self._last_timestamp = obj[TIME_KEY]
        del obj[TIME_KEY]

        return obj

    async def write(self, obj):
        if TIME_KEY in obj:
            raise ValueError(f"key {TIME_KEY!r} is reserved in {obj!r}")

        obj[TIME_KEY] = time.time()
        return await super().write(obj)




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
