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

class App:

    def __init__(self):
        EventManager.on("set mode", self.set_mode)

        self.going = True
        self.clock = pygame.time.Clock()
        self.max_fps = 60
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
                cancel_scope = trio.move_on_after(10)
                with cancel_scope:
                    await self.scene.init()
                if cancel_scope.cancelled_caught:
                    raise ValueError(f"{new}.init took too long")
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

