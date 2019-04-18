import os
import time
import net
import trio
import pygame
import pygame.freetype
import logging
from collections import namedtuple
from pygame.locals import *
from lockables import Lockable
from constants import *
from client.utils import *

from client.scene import Scene
from client.game import Game
from client.username import Username

os.environ['SDL_VIDEO_CENTERED'] = '1'

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

Scene.fonts = namedtuple('Fonts', 'mono')(
    pygame.freetype.SysFont("Fira Mono", 12)
)

MAX_FPS = 60

class SceneManager:

    scenes = {
        'game': Game,
        'username': Username
    }

    def __init__(self, nursery):
        self.screen = pygame.display.set_mode((640, 400))
        self.srect = self.screen.get_rect()

        self.fps = 0
        self.debug = True

        self.game_nursery = nursery

    async def run_scene(self, scene):
        for e in pygame.event.get():
            if e.type == QUIT:
                return False

            caught = self.scene.handle_event()
            if not caught:
                pass

    async def mainloop(self):
        new_scene_name = 'username'
        pdata = PersistentData()

        while True:

            async with trio.open_nursery() as scene_nursery:

                scene = self.scenes[new_scene_name](scene_nursery, pdata)
                with trio.move_on_after(2) as cancel_scope:
                    await scene.init()
                if cancel_scope.cancelled_caught:
                    raise ValueError(f"{new_scene_name}.init took too long")

                new_scene_name = None

                clock = pygame.time.Clock()
                while new_scene_name is None:

                    new_scene_name = await self.run_scene(scene)

                    if new_scene_name == False:
                        return await self.close_scene(scene, scene_nursery)

                    clock.tick(MAX_FPS)

    async def close_scene(self, scene, scene_nursery):
        """ Close the scene, with a few checks """
        async with trio.move_on_after(2) as cancel_scope:
            await scene.aclose()

        if cancel_scope.cancelled_caught:
            raise ValueError(f"Scene {scene} took too long to close")

        tasks_left = len(scene_nursery.child_tasks) 
        if tasks_left > 0:
            raise ValueError(f"Scene {scene} should have closed all tasks "
                             f"in the nursery. Got {tasks_left} more")



class PersistentData:
    pass



class App:

    scenes = {
        'game': Game,
        'username': Username
    }

    def __init__(self):
        self.scene = Lockable(None)

        self.window = Lockable(None)

        pygame.display.set_caption('Nine42')
        pygame.key.set_repeat(300, 50)

        self.fps = Lockable(0)
        self.debug = Lockable(True)

    async def set_mode(self, *args, **kwargs):
        async with self.window.cap_lim:
            self.window.value = {
                "surf": pygame.display.set_mode(*args, **kwargs)
            }
            self.window.value['rect'] = self.window.value['surf'].get_rect()

    async def show_debug_infos(self, fps, surf, srect):
        text = f"{await self.scene.debug_string()} " \
               f"{self.scene} " \
               f"{round(fps):2} fps"

        rect = Scene.fonts.mono.get_rect(text)
        rect.bottomright = srect.bottomright
        Scene.fonts.mono.render_to(surf, rect, text, fgcolor=WHITE,
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
                with trio.move_on_after(2) as cancel_scope:
                    await self.scene.init()

                if cancel_scope.cancelled_caught:
                    raise ValueError(f"{new}.init took too long")
                new = None

                while new is None:
                    for event in pygame.event.get():
                        if event.type == QUIT:
                            return await self._close_scene()

                        caught = await self.scene.handle_event(event)
                        if not caught and event.type == KEYDOWN and event.key == K_BACKSPACE:
                            async with self.debug.cap_lim:
                                self.debug.value = not self.debug.value

                    new = await self.scene.update()
                    if new is False:
                        return await self._close_scene()

                    await self.scene.update()

                    async with self.window.cap_lim:
                        surf = self.window.value['surf']
                        rect = self.window.value['rect']
                        surf.fill(0)
                        await self.scene.render(surf, rect)

                        # async with self.debug.cap_lim:
                        #     await self.show_debug_infos()

                        clock.tick(MAX_FPS)
                        async with self.fps.cap_lim:
                            self.fps.value = clock.get_fps()

                        pygame.display.flip()
                    await trio.sleep(0)

                log.info(f"Switching to new scene: {new}")
                await self._close_scene()

    async def _close_scene(self):
        log.debug("Closing current scene")
        await self.scene.aclose()
        log.debug("Scene closed")

    async def run(self):
        await self.set_mode((640, 480))
        await self.mainloop()
        log.debug("Main loop finished, exiting")

        if hasattr(Scene, 'stream'):
            log.debug("Closing main stream...")
            await Scene.stream.aclose()
            log.debug("Stream closed")
        # TODO: I shouldn't have to do this. What are the tasks that are still
        # running?
        # Scene.nursery.cancel_scope.cancel()
    
async def run():
    pygame.init()
    pygame.freetype.init()

    await App().run()
    pygame.quit()

