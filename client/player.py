import pygame
import logging
from constants import *
from client.utils import *

log = logging.getLogger(__name__)

class Player:

    def __init__(self, username, pos, color):
        self.pos = pos
        self.color = color
        self.username = username

        self.rect = pygame.Rect((0, 0), PLAYER_SIZE)

    def update_state(self, pos):
        self.pos = pos

    def render(self):
        if self.pos is None:
            log.warning(f"{self} position is None")
            return

        self.rect.left = int(round(self.pos[0]))
        self.rect.top = int(round(self.pos[1]))
        pygame.draw.rect(Screen.surface, self.color, self.rect)

    def __str__(self):
        return f"<c.Player {self.username!r} {self.pos}>"

    def __repr__(self):
        return str(self)