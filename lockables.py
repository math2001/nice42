"""Lockables is collection of native object such as dicts and lists that
only prevent collisions

"""

import trio

class Dict:

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._cap_lim = trio.CapacityLimiter(1)

    async def set(self, key, value):
        async with self._cap_lim:
            self._d[key] = value

    async def get(self, key):
        async with self._cap_lim:
            return self._d[key]

    async def remove(self, key):
        async with self._cap_lim:
            del self._d[key]

    async def keys(self):
        # it's a syntax error to do yield from in an async function (3.7.0)
        async with self._cap_lim:
            for key in self._d:
                yield key

    async def items(self):
        async with self._cap_lim:
            for key, val in self._d.items():
                yield key, val
    
    async def values(self):
        async with self._cap_lim:
            for val in self._d.values():
                yield val

    async def len(self):
        async with self._cap_lim:
            return len(self._d)

    def __str__(self):
        return f"<lockables.Dict {self._d}>"

    def __repr__(self):
        return str(self)