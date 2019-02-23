import os
import time
import net
import trio
import pygame
import pygame.freetype
import logging
from collections import namedtuple
from pygame.locals import *
import lockables
from constants import *
from client.utils import *

from client.scene import Scene
from client.game import Game
from client.username import Username

os.environ['SDL_VIDEO_CENTERED'] = '1'

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

fonts = namedtuple('Fonts', 'mono')(
    pygame.freetype.SysFont("Fira Mono", 12)
)


MAX_FPS = 60

class App:

    def __init__(self):
        EventManager.on("set mode", self.set_mode)

        self.scene = None

        self.scenes = {
            'game': Game,
            'username': Username
        }

        Scene.fonts = fonts

        EventManager.emit('set mode', (640, 480))

        pygame.display.set_caption('Nine42')

        # TODO: use lockables.Value. FPS and debug have nothing to do with each
        # other, they should be able to be changed at the same time (a dict
        # prevents that)
        self.app_state = lockables.Dict(fps=0, debug=True)

    def set_mode(self, *args, **kwargs):
        self.window = pygame.display.set_mode(*args, **kwargs)
        Screen.update()

    async def show_debug_infos(self):
        # TODO: maybe move this out of the game loop?
        text = f"{await self.scene.debug_string()} " \
               f"{self.scene} " \
               f"{round(await self.app_state.get('fps')):2} fps"
        rect = fonts.mono.get_rect(text)
        rect.bottomright = Screen.rect.bottomright
        fonts.mono.render_to(Screen.surface, rect, text, fgcolor=WHITE,
                                   bgcolor=BLACK)
    
    async def mainloop(self):
        ''' the basic main loop, handling forceful quit (when the user double
        clicks the close button) '''
        
        new = 'username'

        clock = pygame.time.Clock()

        while True:

            log.info(f"Switch scene {new!r}")

            # start the scene nursery
            async with trio.open_nursery() as snursery:
                self.scene = self.scenes[new](snursery)
                cancel_scope = trio.move_on_after(2)
                with cancel_scope:
                    await self.scene.init()
                if cancel_scope.cancelled_caught:
                    raise ValueError(f"{new}.init took too long")
                new = None

                while new is None:
                    for event in pygame.event.get():
                        if event.type == QUIT:
                            return await self._close_scene()

                        caught = self.scene.handle_event(event)
                        if not caught and event.type == KEYDOWN and event.key == K_BACKSPACE:
                            await self.app_state.set('debug',
                                not await self.app_state.get('debug'))

                    new = await self.scene.update()
                    if new is False:
                        return await self._close_scene()

                    Screen.surface.fill(BLACK)
                    await self.scene.update()
                    await self.scene.render()
                    if await self.app_state.get('debug'):
                        await self.show_debug_infos()
                    clock.tick(MAX_FPS)
                    await self.app_state.set('fps', clock.get_fps())
                    pygame.display.flip()
                    await trio.sleep(0)

    async def _close_scene(self):
        log.debug("Closing current scene")
        await self.scene.aclose()
        log.debug("Scene closed")

    async def run(self):
        await self.mainloop()
        log.debug("Main loop finished, exiting")

        if hasattr(Scene, 'stream'):
            log.debug("Closing main stream...")
            await Scene.stream.aclose()
            log.debug("Stream closed")
        # TODO: I shouldn't have to do this. What are the tasks that are still
        # running?
        Scene.nursery.cancel_scope.cancel()
    
async def run():
    pygame.init()
    pygame.freetype.init()
    async with trio.open_nursery() as nursery:
        Scene.nursery = nursery
        nursery.start_soon(App().run)
    pygame.quit()

