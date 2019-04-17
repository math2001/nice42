import trio
import net
import time
import pygame
import pygame.freetype
import random
from logging import getLogger
from pygame.locals import *
from constants import *
from client.scene import Scene

class Username(Scene):

    async def init(self):
        Scene.stream = net.JSONStream(await trio.open_tcp_stream("127.0.0.1", PORT))
        username = str(random.random())
        await Scene.stream.write({"type": "username", "username": username})

    async def update(self):
        return 'game'
