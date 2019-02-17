import trio
import net
import pygame
from log import getLogger
from pygame.locals import *
from constants import *

log = getLogger()

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

async def fetch_player_updates_forever(players, stream):
    while True:
        state = await net.read(stream)
        if state['type'] != 'players':
            raise ValueError(f"Expected type to be 'players' in {state}")

        players[:] = state['players']

async def gameloop(stream, nursery):
    keyboard_state = 0
    players = []
    log.info("Start fetching player updates")
    nursery.start_soon(fetch_player_updates_forever, players, stream)
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                log.info("Stopping game loop")
                nursery.cancel_scope.cancel()
                return

        # send keyboard state if it has changed
        new = get_keyboard_state()
        if new != keyboard_state:
            log.info(f"Keyboard state update: {new}")
            nursery.start_soon(net.write, stream, {"type": "keyboard", "state": new})
            keyboard_state = new

        # render the players
        for player in players:
            rect = pygame.Rect(player['pos'], PLAYER_SIZE)
            pygame.draw.rect(screen, player['color'], rect)

        pygame.display.flip()
        await trio.sleep(0)
    

async def run():
    global screen
    stream = await trio.open_tcp_stream("127.0.0.1", PORT)
    async with stream:
        # keep shit simple
        # name = input("your name: ")
        name = 'math2001'
        await net.write(stream, {
            "type": "username",
            "username": name
        })
        screen = pygame.display.set_mode(MAP_SIZE)
        log.info("Starting game loop")
        async with trio.open_nursery() as nursery:
            await gameloop(stream, nursery)
    log.info("Client ended")
