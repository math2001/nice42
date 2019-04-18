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

        self.pdata = PersistentData()
        self.pdata.fonts = load_fonts()

        self.clock = pygame.time.Clock()

    def show_debug_infos(self):
        text = f"{self.scene.debug_string()} {self.scene} {round(fps):2} fps"

        with fontedit(self.pdata.fonts.mono, bgcolor=BLACK) as font:
            rect = font.render(text)
            rect.bottomright = self.srect.bottomright
            font.render_to(surf, rect, None)

    def run_scene(self):
        """ Runs the current scene, returning the next scene that the current
        scene requested (if any) """

        for e in pygame.event.get():
            if e.type == QUIT:
                return False

            caught = self.scene.handle_event()
            if not caught and event.type == KEYDOWN and event.key == K_F2:
                self.debug = not self.debug

            self.scene.update()

            self.screen.fill(0)
            self.scene.render(self.screen, self.srect)

            if self.debug:
                self.show_debug_infos()

            self.clock.tick(MAX_FPS)
            pygame.display.flip()

    async def mainloop(self):
        new_scene_name = 'username'

        while True:

            log.info(f"Scene: {new_scene_name!r}")

            async with trio.open_nursery() as scene_nursery:

                scene = self.scenes[new_scene_name](scene_nursery, self.pdata)
                new_scene_name = None

                while new_scene_name is None:
                    new_scene_name = self.run_scene(scene)

                    if new_scene_name is False:
                        return self.close_scene(scene, scene_nursery)

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

    
async def run(nursery):
    pygame.init()
    pygame.freetype.init()
    await SceneManager(nursery).mainloop()
    pygame.quit()
