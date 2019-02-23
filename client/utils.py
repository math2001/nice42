import pygame
import warnings
from contextlib import contextmanager
from pygame.display import get_surface

WHITE = 255, 255, 255
BLACK = pygame.Color('black')
PINK = pygame.Color('pink')
RED = pygame.Color('red')
BLUE = pygame.Color('blue')

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

class Screen:

    @classmethod
    def update(cls):
        cls.surface = get_surface()
        cls.rect = cls.surface.get_rect()

class EventManager:

    events = {}

    @classmethod
    def on(cls, event, func):
        cls.events.setdefault(event, []).append(func)
    
    @classmethod
    def emit(cls, event, *args, **kwargs):
        try:
            cbs = cls.events[event]
        except KeyError:
            warnings.warn(f"Emitting event {event!r} that hasn't got any "
                          f"listener. Only know about {list(cls.events.keys())}")

        for cb in cbs:
            cb(*args, **kwargs)

    @classmethod
    def off(cls, event, func=None):
        try:
            funcs = cls.events[event]
        except KeyError:
            warnings.warn(f"Removing callback from non-existant event {event!r}")
        if func is None:
            del cls.events[event]
            return
        try:
            funcs.remove(func)
        except ValueError:
            warning.warn(f"Removing non-existant callback from {event!r}. "
                         f"({len(funcs)} other callback))")

