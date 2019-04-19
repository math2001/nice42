""" This is a base class from which every scenes inherits from
"""

import pygame
import pygame.freetype

pygame.freetype.init()

class Scene:

    def __init__(self, nursery):
        self.nursery = nursery

    def init(self):
        pass
  
    def handle_event(self, e):
        """ *pygame* event"""
           
    def render(self, surf, rect):
        pass
    
    def update(self):
        pass

    def debug_string(self):
        return ''

    def __str__(self):
        return f"<Scene {self.__class__.__name__!r}>"

    def __repr__(self):
        return str(self)

    def close(self):
        pass