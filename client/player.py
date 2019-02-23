import time
import pygame
import logging
from constants import *
from client.utils import *

log = logging.getLogger(__name__)

DEBUG_PREDICTED_POSITION = 1 << 0

DEBUG = DEBUG_PREDICTED_POSITION

class Player:

    def __init__(self, username, pos, color):

        self.server_pos = pos
        self.pos = list(self.server_pos)

        self.color = color
        self.username = username

        self.rect = pygame.Rect((0, 0), PLAYER_SIZE)

        # the predicted change in position
        self.predicted_change = None

        self.last_server_update = time.time()

    def update_state(self, pos):
        """ Update state from the server 

        Rule #1:

        Every time I receive a server update, I make a prediction about where the
        player will be at the next server update. We assume that the direction
        of the player between the 2 server updates will be the same in the next
        update (this will obviously be wrong sometimes, but it will be
        corrected by rule #2)

        Rule #2:

        Whatever happens, I have to get to the predicted position  exactly on
        the next server update.

        """
        direction = [
            arg(pos[0] - self.server_pos[0]),
            arg(pos[1] - self.server_pos[1])
        ]
        self.last_pos = self.pos
        self.server_pos = pos
        self.predicted_change = [
            direction[0] * PLAYER_SPEED * SERVER_REFRESH_RATE,
            direction[1] * PLAYER_SPEED * SERVER_REFRESH_RATE,
        ]

        self.last_server_update = time.time()

    def update(self):
        """ Update state in between server updates """
        if self.predicted_change:
            percentage_done = (time.time() - self.last_server_update) / SERVER_REFRESH_RATE
            self.pos = [
                self.last_pos[0] + percentage_done * self.predicted_change[0],
                self.last_pos[1] + percentage_done * self.predicted_change[1]
            ]
        self.rect.left = int(round(self.pos[0]))
        self.rect.top = int(round(self.pos[1]))


    def render(self):
        if self.pos is None:
            log.warning(f"{self} position is None")
            return

        pygame.draw.rect(Screen.surface, self.color, self.rect)
        if DEBUG & DEBUG_PREDICTED_POSITION:
            pygame.draw.rect(
                Screen.surface,
                self.color,
                pygame.Rect(self.server_pos, PLAYER_SIZE),
                1
            )

    def __str__(self):
        return f"<c.Player {self.username!r} {self.pos}>"

    def __repr__(self):
        return str(self)