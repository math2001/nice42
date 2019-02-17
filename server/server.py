import trio
import random
import net
from server.player import Player
from log import getLogger
from itertools import count
from constants import *

players = {}

log = getLogger()

PLAYER_COUNT = count()

async def handle_client(player):
    log.debug("Waiting for name")
    await player.get_name()
    player.spawn((
        random.randint(0, MAP_SIZE[0] - PLAYER_SIZE[0]),
        random.randint(0, MAP_SIZE[1] - PLAYER_SIZE[1]),
    ))
    log.info(f"{player} added to players dict")
    players[player.id] = player

    async with trio.open_nursery() as n:
        # if the client leaves, there's 2 different thing that can happen:
        # 1. I try to read from a dead connection
        # 2. I try to write to a dead connection
        # these raise 2 different errors, which means that both of them have
        # to be handled
        n.start_soon(player.get_user_input_forever)
        n.start_soon(player.send_player_state_forever, players)

async def server(stream):
    log.info("New connection")

    player = Player(next(PLAYER_COUNT), stream)

    try:
        await handle_client(player)
    except (net.ConnectionClosed, trio.BrokenResourceError):
        # we couldn't read or we couldn't write
        log.info(f"{player} connection closed")
    except Exception as e:
        log.exception("Handler crashed")
    finally:
        log.info(f"{player} removed")
        del players[player.id]

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
        await trio.sleep(0.01)

async def run():
    async with trio.open_nursery() as n:
        n.start_soon(trio.serve_tcp, server, PORT)
        n.start_soon(gameloop, n)
