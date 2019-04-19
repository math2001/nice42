import logging
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

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

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
    VALID_STATES = 'update', 'dead'
    while True:
        state = await stream.read()
        if state['type'] not in VALID_STATES:
            raise ValueError(f"Expected type to be one of {VALID_STATES} in {state}")
        log.debug(f"Update: {state}")
        await sendch.send(state)

class Game(Scene):

    def __init__(self, nursery, pdata):
        self.nursery = nursery
        self.pdata = pdata

        self.keyboard_state = 0
        self.update_sendch, self.update_getch = trio.open_memory_channel(0)

        self.players = {}

        self.lps = 0

        self.nursery.start_soon(fetch_updates_forever, self.pdata.stream,
                                self.update_sendch)

    def debug_string(self):
        return f"lps: {self.lps}"

    def update(self):
        """ This function is ran every frame """
        new = get_keyboard_state()
        if new != self.keyboard_state:
            self.keyboard_state = new
            self.nursery.start_soon(self.pdata.stream.write, {
                "type": "keyboard",
                "state": self.keyboard_state
            })

        # see if there any fresh updates from the server
        try:
            update = self.update_getch.receive_nowait()
        except trio.WouldBlock:
            # no updates available, "guess" what should be happening
            for player in self.players.values():
                player.update()
            return

        if update['type'] != 'update':
            log.warning(f"Recieved invalid update: {update}")
            return

        # update state from server
        self.lps= update['lps']

        for username in update['gone_players']:
            del self.players[username]
            log.info(f"Remove player {username}")

        for username, state in update['players'].items():
            self.players[username].update_state(state['pos'])

        for username, state in update['new_players'].items():
            self.players[username] = Player(username, state['pos'],
                state['color'], self.pdata.fonts)
            log.info(f"Add new player {self.players[username]}")

    def render(self, surf, srect):
        for player in self.players.values():
            player.render(surf, srect)

    def close(self):
        # brute force
        self.nursery.cancel_scope.cancel()