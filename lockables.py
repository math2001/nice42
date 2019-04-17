"""Lockables is collection of native object such as dicts and lists that
only prevent collisions

"""

import trio

class Lockable:

    def __init__(self, value):
        self.value = value
        self.cap_lim = trio.CapacityLimiter(1)
