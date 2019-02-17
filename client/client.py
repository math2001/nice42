import trio
import net
import time
import pygame
import pygame.freetype
from log import getLogger
from pygame.locals import *
from constants import *

log = getLogger()

pygame.freetype.init()
font = pygame.freetype.SysFont("Fira Mono", 12)
font.fgcolor = 255, 255, 255

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

async def fetch_updates_forever(sendch, stream):
    """ This'll get more fancy as network will become the bottleneck
    (it's not yet) """
    while True:
        state = await net.read(stream)
        if state['type'] != 'update':
            raise ValueError(f"Expected type to be 'update' in {state}")

        del state['type']
        await sendch.send(state)

async def gameloop(stream, nursery):
    keyboard_state = 0
    sendch, getch = trio.open_memory_channel(0)
    log.info("Start fetching player updates")
    nursery.start_soon(fetch_updates_forever, sendch, stream)

    game_state = None
    last = time.time()
    update_count = 0
    clock = pygame.time.Clock()
    ping = 'inf'

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                log.info("Stopping game loop")
                nursery.cancel_scope.cancel()
                return
        if getch.statistics().tasks_waiting_send > 0:
            game_state = await getch.receive()
            update_count += 1

        if time.time() - last >= 1:
            last = time.time()
            if update_count:
                ping = round(1000 / update_count)
            else:
                ping = 'inf'
            update_count = 0

        # send keyboard state if it has changed
        new = get_keyboard_state()
        if new != keyboard_state:
            log.debug(f"Keyboard state update: {new}")
            nursery.start_soon(net.write, stream, {"type": "keyboard", "state": new})
            keyboard_state = new

        screen.fill(0)
        if game_state:
            # render the players
            for player in game_state['players']:
                rect = pygame.Rect(player['pos'], PLAYER_SIZE)
                pygame.draw.rect(screen, player['color'], rect)

            fps = round(clock.get_fps())
            lps = game_state['lps']
            text = f"fps: {fps} | lps: {lps} | ping: {ping} ms"

            r = font.get_rect(text)
            r.bottomright = srect.bottomright
            font.render_to(screen, r, text)
        else:
            text = 'no game state'
            r = font.get_rect(text)
            r.center = srect.center
            font.render_to(screen, r, text)

        clock.tick(60)
        pygame.display.flip()
        await trio.sleep(0)

async def run():
    global screen
    global srect
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
        srect = screen.get_rect()
        log.info("Starting game loop")
        async with trio.open_nursery() as nursery:
            await gameloop(stream, nursery)
    log.info("Client ended")
