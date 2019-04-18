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
log.setLevel(logging.INFO)

class Username(Scene):

    async def init(self):
        Scene.stream = net.JSONStream(await trio.open_tcp_stream("127.0.0.1", PORT))
        self.username = Lockable("")
        self.username_submitted = trio.Event()

    async def update(self):
        pass

    async def handle_event(self, e):
        if e.type != KEYDOWN:
            return
        if e.key == K_BACKSPACE:
            async with self.username.cap_lim:
                self.username.value = self.username.value[:-1]
        elif e.key in (K_KP_ENTER, K_RETURN):
            await self.submit()
        elif e.unicode:
            async with self.username.cap_lim:
                self.username.value += e.unicode

    async def submit(self):
        async def send(username):
            await Scene.stream.write({
                "type": "username",
                "username": username,
            })
            self.username_submitted.set()

        async with self.username.cap_lim:
            self.nursery.start_soon(send, self.username.value)

    async def update(self):
        if self.username_submitted.is_set():
            return 'game'

    async def render(self, screen, srect):

        start = [srect.centerx - 50, srect.centery]

        async with self.username.cap_lim:
            with fontedit(Scene.fonts.mono, fgcolor=pygame.Color('white'),
                          origin=True) as font:
                rect = font.render_to(screen, start, self.username.value)

        start[0] += rect.width
        end = start[0] + 5, start[1]
        pygame.draw.line(screen, pygame.Color('white'), start, end, 2)
