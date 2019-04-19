import logging
import trio
import net
import time
import pygame
import pygame.freetype
import random
from logging import getLogger
from pygame.locals import *
from constants import *
from client.scene import Scene
from client.utils import *
from lockables import Lockable

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

STATE_CONNECTING = 0, "Connecting to server..."
STATE_WAITING_INPUT = 10, "Type your username and press enter!"
STATE_WAITING = 20, "Waiting for server response..."
STATE_ACCEPTED = 30, "Going to game!"

async def submit_username(username, stream, sendch):
    """ Submits the username and waits for the server to accept

    it sends one value on the channel and then closes it.

    - {"type": "accepted"} if the server accepted
    - {"type": "refused", "reason": <server message>} if the server refused
    - {"type": "error", "error": <error>} failed to write, read, etc...
    """

    # TODO: retry if it's only a temporary error

    async with sendch:
        try:
            await stream.write({"type": "username", "username": username})
        except net.ConnectionClosed as e:
            return await sendch.send({"type": "error", "error": e})

        try:
            resp = await stream.read()
        except net.ConnectionClosed as e:
            log.exception("failed to read username response")
            return await sendch.send({"type": "error", "error": e})

        if "type" not in resp:
            return await sendch.send({"type": "error", "error": f"invalid response {resp}"})

        if resp["type"] == "accepted":
            return await sendch.send({"type": "accepted"})
        elif resp["type"] == "refused":
            return await sendch.send({"type": "refused", "reason": resp["reason"]})
        else:
            return await sendch.send({"type": "error", "error": f"invalid type in {resp}"})

class Username(Scene):

    def __init__(self, nursery, pdata):
        self.scene_nursery = nursery
        self.pdata = pdata

        self.username = ""
        self.resp_sendch, self.resp_getch = trio.open_memory_channel(0)
        self.request_sent = trio.Event()

        self.state = STATE_CONNECTING

        self.scene_nursery.start_soon(self.connect_to_server)

    async def connect_to_server(self):
        log.debug("Connecting to server...")
        self.pdata.stream = net.JSONStream(await trio.open_tcp_stream("localhost", PORT))
        self.state = STATE_WAITING_INPUT
        log.info(f"Connected to server ({self.state})")

    def handle_event(self, e):
        if self.state[0] != STATE_WAITING_INPUT[0]:
            return

        if e.type != KEYDOWN:
            return

        if e.key == K_BACKSPACE:
            if len(self.username) > 0:
                self.username = self.username[:-1]
        elif e.key in (K_RETURN, K_KP_ENTER):

            self.scene_nursery.start_soon(submit_username, self.username,
                                          self.pdata.stream, self.resp_sendch)
            self.scene_nursery.start_soon(self.set_state)
            self.state = STATE_WAITING

        elif e.unicode:
            self.username += e.unicode

    async def set_state(self):
        log.debug("Waiting for server response...")
        resp = await self.resp_getch.receive()
        log.debug(f"resp: {resp}")
        if resp['type'] == 'accepted':
            self.state = STATE_ACCEPTED
        elif resp['type'] == 'refused':
            self.state = STATE_REFUSED
        elif resp['type'] == 'error':
            # should display error message and all
            raise ValueError(f"Error during Username scene: {resp}")
        else:
            raise ValueError(f"Invalid response type: {resp}")


    def update(self):
        if self.state == STATE_ACCEPTED:
            return 'game'

    def render(self, screen, srect):
        # render the username
        start = [srect.centerx - 50, srect.centery]

        with fontedit(self.pdata.fonts.mono, origin=True) as font:
            rect = font.render_to(screen, start, self.username)

        if self.state == STATE_WAITING_INPUT:
            # render the cursor
            start[0] += rect.width
            end = start[0] + 5, start[1]
            pygame.draw.line(screen, WHITE, start, end, 2)

        with fontedit(self.pdata.fonts.mono, fgcolor=GREY) as font:
            rect = font.get_rect(self.state[1])
            rect.midbottom = srect.midbottom
            rect.top -= 20
            font.render_to(screen, rect, None)