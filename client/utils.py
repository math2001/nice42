import pygame
import warnings
from contextlib import contextmanager
from pygame.display import get_surface

WHITE = 255, 255, 255
BLACK = pygame.Color('black')
PINK = pygame.Color('pink')
RED = pygame.Color('red')
BLUE = pygame.Color('blue')
GREY = pygame.Color('grey')

def mod(n):
    """ Return the magnitude of a number """
    return n if n >= 0 else -n

def arg(n):
    """ Return the direction of a number """
    if n > 0:
        return 1
    elif n < 0:
        return -1
    return 0

@contextmanager
def fontedit(font, **kwargs):
    """ Applies some settings to a font, and then removes them """
    defaults = {}
    for key in kwargs:
        try:
            defaults[key] = getattr(font, key)
        except AttributeError as e:
            raise AttributeError(f"Invalid parameter for font {key!r}")
        try:
            setattr(font, key, kwargs[key])
        except AttributeError:
            raise AttributeError(f"Could not set {key!r}. Probably read-only")
    yield font
    for key, value in defaults.items():
        try:
            setattr(font, key, value)
        except AttributeError:
            raise AttributeError(f"Could not reset {key!r} to its original value")

def classname(obj):
    return obj.__class__.__name__
