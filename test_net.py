import trio
import trio.testing

import json

from hypothesis import given, settings
import hypothesis.strategies as st

import net
import logging

logging.basicConfig(level=logging.WARNING)

keys = st.one_of(st.text(min_size=1, max_size=40))
values = st.one_of(
    st.integers(),
    st.floats(allow_nan=False),
    st.text(min_size=1, max_size=40),
    st.booleans()
)

serializable = st.dictionaries(keys, values, max_size=20)

async def _send_string_by_chunks(stream, string, *, chunk_len=10):
    # length of chunks
    i = 0
    while i < len(string):
        j = i + chunk_len
        if j > len(string):
            j = len(string)
        await stream.send_all(bytes(string[i:j], encoding='utf-8'))
        # await trio.sleep(0)
        i = j

async def _assert_reading(stream, objects):
    i = 0
    with trio.move_on_after(1) as cancel_scope:
        while i < len(objects):
            assert await stream.read() == objects[i]
            i += 1

    assert cancel_scope.cancelled_caught is False

@given(st.lists(serializable, max_size=10))
@settings(deadline=500, max_examples=50)
async def test_read_chuncky_connection(objects):
    """ Make sure that JSON stream works when texts doesn't come in nicely """
    with trio.move_on_after(1) as cancel_scope:
        a, stream_controlled = trio.testing.memory_stream_pair()
        stream_tested = net.JSONStream(a)
        string = '\n'.join(json.dumps(obj) for obj in objects) + '\n'

        async with trio.open_nursery() as n:
            n.start_soon(_send_string_by_chunks, stream_controlled, string)
            n.start_soon(_assert_reading, stream_tested, objects)
    assert cancel_scope.cancelled_caught is False