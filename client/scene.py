""" This is a base class from which every scenes inherits from
"""

# TODO: manage EventManager from the scene, and remove them automatically

import pygame
import pygame.freetype
from client.utils import EventManager, Screen

pygame.freetype.init()

class Scene:

    def __init__(self, nursery):
        self.nursery = nursery

    async def init(self):
        pass
  
    def handle_event(self, e):
        """ *pygame* event"""
           
    def render(self):
        raise ValueError("No renderer for scene {}".format(self.__class__.__name__))
    
    async def update(self):
        pass

    def debug_string(self):
        return ''

    def __str__(self):
        return f"<Scene {self.__class__.__name__!r}>"

    def __repr__(self):
        return str(self)

    async def aclose(self):
        self.nursery.cancel_scope.cancel()