import trio
import trio.testing

import json

from hypothesis import given
import hypothesis.strategies as st

import net
import logging

logging.basicConfig(level=logging.DEBUG)

basics = st.one_of(st.integers(), st.floats(), st.text(), st.booleans())

serializable = st.dictionaries(basics, basics, max_size=20)

async def _send_string_by_chunks(stream, string, *, chunk_len=10):
    # length of chunks
    i = 0
    while i < len(string):
        j = i + chunk_len
        if j > len(string):
            j = len(string)
        await stream.send_all(bytes(string[i:j], encoding='utf-8'))
        await trio.sleep(0)
        i = j

async def _assert_reading(stream, objects):
    i = 0
    with trio.move_on_after(1) as cancel_scope:
        while i < len(objects):
            assert await stream.read() == objects[i]
            i += 1

    if cancel_scope.cancelled_caught:
        assert False

@given(st.lists(serializable, max_size=20))
async def test_read_chuncky_connection(objects):
    """ Make sure that JSON stream works when texts doesn't come in nicely """
    a, stream_controlled = trio.testing.memory_stream_pair()
    stream_tested = net.JSONStream(a)
    string = '\n'.join(json.dumps(obj) for obj in objects)

    async with trio.open_nursery() as n:
        n.start_soon(_send_string_by_chunks, stream_controlled, string)
        n.start_soon(_assert_reading, stream_tested, objects)
