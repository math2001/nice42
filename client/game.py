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
    VALID_STATES = 'update', 'dead'
    while True:
        state = await stream.read()
        if state['type'] not in VALID_STATES:
            raise ValueError(f"Expected type to be one of {VALID_STATES} in {state}")

        await sendch.send(state)

class Game(Scene):

    def __init__(self, nursery):
        self.nursery = nursery
        self.keyboard_state = 0
        self.update_sendch, self.update_getch = trio.open_memory_channel(0)

        self.players = lockables.Lockable({})

        self.lps = lockables.Lockable(0)
        
    async def init(self):
        log.debug("Waiting for 'init game' message")
        initstate = await Scene.stream.read()
        log.info("Got 'init game' message")
        log.debug(f"state: {initstate}")

        if initstate['type'] != 'init game':
            raise ValueError(f"Expected type to be 'init game' in {state}")

        async with self.players.cap_lim:
            for username, player in initstate['new_players'].items():
                self.players.value[username] = Player(
                    username=username,
                    pos=player['pos'],
                    color=player['color']
                )

            log.debug(f"Got {len(self.players.value)} new players")
        log.debug("Start fetching updates from server forever")
        self.nursery.start_soon(fetch_updates_forever, Scene.stream,
                                self.update_sendch)

    async def debug_string(self):
        async with self.lps.cap_lim:
            return f"lps: {self.lps.value}"

    async def update(self):
        """ This function is ran every frame """
        new = get_keyboard_state()
        if new != self.keyboard_state:
            self.keyboard_state = new
            self.nursery.start_soon(self.stream.write, {
                "type": "keyboard",
                "state": self.keyboard_state
            })

        # see if there any fresh updates from the server
        try:
            update = self.update_getch.receive_nowait()
        except trio.WouldBlock:
            # no updates available, guess what should be happening
            async with self.players.cap_lim:
                for player in self.players.value.values():
                    player.update()
        else:
            if update['type'] == 'dead':
                return 'dead'
            elif update['type'] == 'update':
                # update state from server
                async with self.lps.cap_lim:
                    self.lps.value = update['lps']

                # TODO: this might be suitable for micro optimisation?
                # ie. don't block for every write operation, and write all of them
                # "at once" in a nursery
                async with self.players.cap_lim:
                    for username, state in update['players'].items():
                        self.players.value[username].update_state(state['pos'])

                    for username, state in update['new_players'].items():
                        self.players.value[username] = Player(username, state['pos'],
                                                              state['color'])
                        log.info(f"Add new player {self.players.value[username]}")

    async def render(self, surf, srect):
        async with self.players.cap_lim:
            for player in self.players.value.values():
                player.render(surf, srect)

    async def aclose(self):
        # brute force
        self.nursery.cancel_scope.cancel()