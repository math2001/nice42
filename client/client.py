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

def load_fonts():
    fonts = namedtuple('Fonts', 'mono')(
        pygame.freetype.SysFont("Fira Mono", 12)
    )

    for font in fonts:
        font.fgcolor = WHITE

    return fonts

MAX_FPS = 60

class SceneManager:

    """
    Could (should) this just be written just as one big function?
    """

    scenes = {
        'game': Game,
        'username': Username
    }

    def __init__(self, nursery):
        self.screen = pygame.display.set_mode((640, 400))
        self.srect = self.screen.get_rect()

        pygame.display.set_caption("Nine42")
        pygame.key.set_repeat(300, 30)

        self.fps = 0
        self.debug = True

        # I don't even need game nursery!
        self.game_nursery = nursery

        self.pdata = PersistentData()
        self.pdata.fonts = load_fonts()

        self.clock = pygame.time.Clock()

        self.mainloop_running = False
        self.game_nursery.start_soon(self.mainloop)

    def show_debug_infos(self):
        text = f"{self.scene.debug_string()} {self.scene} {round(self.fps):2} fps"

        with fontedit(self.pdata.fonts.mono) as font:
            rect = font.get_rect(text)
            rect.bottomright = self.srect.bottomright
            font.render_to(self.screen, rect, None, bgcolor=BLACK)

    def run_scene(self):
        """ Runs the current scene, returning the next scene that the current
        scene requested (if any)

        It returns false if the scene decided to exit, and true if the user
        press the cross.
        """

        for e in pygame.event.get():
            if e.type == QUIT:
                return True

            caught = self.scene.handle_event(e)
            if not caught and e.type == KEYDOWN and e.key == K_F2:
                self.debug = not self.debug

        new_scene = self.scene.update()
        if new_scene is not None:
            return new_scene

        self.screen.fill(0)
        self.scene.render(self.screen, self.srect)

        if self.debug:
            self.show_debug_infos()

        self.fps = self.clock.get_fps()

        self.clock.tick(MAX_FPS)
        pygame.display.flip()

    async def mainloop(self):
        if self.mainloop_running:
            raise ValueError("Main loop should only be called once per instance")
        new_scene_name = 'username'

        while True:

            log.info(f"Scene: {new_scene_name!r}")

            async with trio.open_nursery() as scene_nursery:

                self.scene = self.scenes[new_scene_name](scene_nursery, self.pdata)
                new_scene_name = None

                while new_scene_name is None:
                    new_scene_name = self.run_scene()

                    if new_scene_name is False:
                        log.info(f"{self.scene} closed the game")
                        return self.close_scene(self.scene, scene_nursery)
                    elif new_scene_name is True:
                        # TODO: tell the scene to close itself
                        log.info(f"Closing the {self.scene} forfully")
                        return scene_nursery.cancel_scope.cancel()

                    await trio.sleep(0)

    def close_scene(self, scene, scene_nursery):
        """ The scene should be ready to be dropped. """

        # checks whether it actually is
        tasks_left = len(scene_nursery.child_tasks) 
        if tasks_left > 0:
            raise ValueError(f"Scene {scene} should have closed all tasks "
                             f"in the nursery. Got {tasks_left} more")



class PersistentData:
    """ Data that is shared accross scenes.

    It's monkey patched by every scene, for the next one.
    """

    
async def run():
    pygame.init()
    pygame.freetype.init()
    async with trio.open_nursery() as nursery:
        SceneManager(nursery)
    pygame.quit()
