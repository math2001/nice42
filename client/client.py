import os
import time
import net
import trio
import pygame
import pygame.freetype
from collections import namedtuple
from log import getLogger
from pygame.locals import *
from constants import *
from client.utils import *

from client.scene import Scene
from client.game import Game
from client.username import Username

os.environ['SDL_VIDEO_CENTERED'] = '1'

log = getLogger()

fonts = namedtuple('Fonts', 'mono')(
    pygame.freetype.SysFont("Fira Mono", 12)
)

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

class App:

    def __init__(self):
        EventManager.on("set mode", self.set_mode)

        self.going = True
        self.clock = pygame.time.Clock()
        self.max_fps = 40
        self.scene = None
        self.debug = True

        self.scenes = {
            'game': Game,
            'username': Username
        }

        Scene.fonts = fonts

        EventManager.emit('set mode', (640, 480))

        pygame.display.set_caption('Nine42')

    def set_mode(self, *args, **kwargs):
        self.window = pygame.display.set_mode(*args, **kwargs)
        Screen.update()

    def show_debug_infos(self):
        text = f"{self.scene.debug_string()} " \
               f"{classname(self.scene)} " \
               f"{round(self.clock.get_fps()):2} fps"
        rect = fonts.mono.get_rect(text)
        rect.bottomright = Screen.rect.bottomright
        fonts.mono.render_to(Screen.surface, rect, text, fgcolor=WHITE,
                                   bgcolor=BLACK)
    
    async def mainloop(self):
        ''' the basic main loop, handling forceful quit (when the user double
        clicks the close button) '''
        
        new = 'username'

        while self.going:

            log.info(f"Switch scene {new!r}")

            # start the scene nursery
            async with trio.open_nursery() as snursery:
                self.scene = self.scenes[new](snursery)
                cancel_scope = trio.move_on_after(1)
                with cancel_scope:
                    await self.scene.init()
                if cancel_scope.cancelled_caught:
                    raise ValueError(f"{scene}.init took too long")
                new = None

                while new is None:
                    for event in pygame.event.get():
                        if event.type == QUIT:
                            return snursery.cancel_scope.cancel()

                        caught = self.scene.handle_event(event)
                        if not caught and event.type == KEYDOWN and event.key == K_BACKSPACE:
                            self.debug = not self.debug

                    new = await self.scene.update()
                    if new is False:
                        return snursery.cancel_scope.cancel()

                    Screen.surface.fill(BLACK)
                    await self.scene.update()
                    self.scene.render()
                    if self.debug:
                        self.show_debug_infos()
                    self.clock.tick(self.max_fps)
                    pygame.display.flip()
                    await trio.sleep(0)

    async def run(self):
        await self.mainloop()
        Scene.nursery.cancel_scope.cancel()


    
async def run():
    pygame.init()
    pygame.freetype.init()
    async with trio.open_nursery() as nursery:
        Scene.nursery = nursery
        nursery.start_soon(App().run)
    pygame.quit()

