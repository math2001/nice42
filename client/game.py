import trio
import net
import time
import pygame
import pygame.freetype
from logging import getLogger
from pygame.locals import *
from constants import *
from client.utils import *
from client.scene import Scene

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
        sendch, self.getch = trio.open_memory_channel(0)
        self.nursery.start_soon(fetch_updates_forever, Scene.stream, sendch)

        self.game_state = None

    def debug_string(self):
        lps = None
        if self.game_state:
            lps = self.game_state['lps']
        return f"lps: {lps}"

    async def update(self):
        new = get_keyboard_state()
        if new != self.keyboard_state:
            self.keyboard_state = new
            self.nursery.start_soon(self.stream.write, {
                "type": "keyboard",
                "state": self.keyboard_state
            })
        if self.getch.statistics().tasks_waiting_send > 0:
            self.game_state = await self.getch.receive()

    def render(self):
        if not self.game_state:
            return
        for player in self.game_state['players']:
            rect = pygame.Rect(player['pos'], PLAYER_SIZE)
            pygame.draw.rect(Screen.surface, player['color'], rect)