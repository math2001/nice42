import trio
import net
import time
import pygame
import pygame.freetype
import lockables
from logging import getLogger
from pygame.locals import *
from constants import *
from client.utils import *
from client.scene import Scene
from client.player import Player

log = getLogger(__name__)

def get_keyboard_state():
    key = pygame.key.get_pressed()
    state = 0
    if key[K_UP]:
        state |= UP
    if key[K_RIGHT]:
        state |= RIGHT
    if key[K_DOWN]:
        state |= DOWN
    if key[K_LEFT]:
        state |= LEFT
    return state

async def fetch_updates_forever(stream, sendch):
    """ This'll get more fancy as network will become the bottleneck
    (it's not yet) """
    while True:
        state = await stream.read()
        if state['type'] != 'update':
            raise ValueError(f"Expected type to be 'update' in {state}")

        del state['type']
        await sendch.send(state)

class Game(Scene):

    def __init__(self, nursery):
        self.nursery = nursery
        self.keyboard_state = 0
        sendch, self.update_getch = trio.open_memory_channel(0)
        self.nursery.start_soon(fetch_updates_forever, Scene.stream, sendch)

        self.players = lockables.Dict()

        self.game_state = lockables.Dict()

    async def init(self):
        await self.game_state.set('lps', None)

    async def debug_string(self):
        return f"lps: {await self.game_state.get('lps')}"

    async def update(self):
        new = get_keyboard_state()
        if new != self.keyboard_state:
            self.keyboard_state = new
            self.nursery.start_soon(self.stream.write, {
                "type": "keyboard",
                "state": self.keyboard_state
            })
        try:
            update = self.update_getch.receive_nowait()
        except trio.WouldBlock:
            pass
        else:
            await self.game_state.set('lps', update['lps'])
            # TODO: this might be suitable for micro optimisation?
            for username, state in update['players'].items():
                (await self.players.get(username)).update_state(state['pos'])

            for username, state in update['new'].items():
                p = Player(username, state['pos'], state['color'])
                await self.players.set(username, p)
                log.info(f"Add new player {p}")

    async def render(self):
        async for player in self.players.values():
            player.render()
