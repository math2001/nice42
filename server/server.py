import trio
import random
from server.player import Player
from log import getLogger
from itertools import count
from constants import *

players = {}

log = getLogger()

PLAYER_COUNT = count()

async def handle_client(player):
    log.info("Waiting for name")
    await player.get_name()
    player.spawn((
        random.randint(0, MAP_SIZE[0] - PLAYER_SIZE[0]),
        random.randint(0, MAP_SIZE[1] - PLAYER_SIZE[1]),
    ))
    log.info(f"{player} added to players dict")
    players[player.id] = player

    async with trio.open_nursery() as n:
        n.start_soon(player.get_user_input_forever)
        n.start_soon(player.send_player_state_forever, players)

async def server(stream):
    log.info("New connection")

    player = Player(next(PLAYER_COUNT), stream)

    try:
        await handle_client(player)
    except Exception as e:
        log.exception("Handler crashed")
        try:
            del players[player.id]
        except KeyError:
            log.info("Player quited on before sending its name")

async def gameloop(nursery):
    log.info("Start game loop")
    while True:
        for player in players.values():

            player.move()

            # if 2 player collide, one of them has to die
            # keep shit simple for now. Random'll do
            for target in players.values():
                if target is player:
                    continue
                if player.collides(target):
                    if random.randint(0, 1) == 0:
                        nursery.start_soon(player.killed)
                    else:
                        nursery.start_soon(target.killed)
        await trio.sleep(0)

async def run():
    async with trio.open_nursery() as n:
        n.start_soon(trio.serve_tcp, server, PORT)
        n.start_soon(gameloop, n)
