import trio
import time
import random
import net
from server.player import Player
from log import getLogger
from itertools import count
from collections import deque
from constants import *

# TODO: change this per player
REFRESH_RATE = .1 # s

players = {}
lps = None

log = getLogger()

PLAYER_COUNT = count()

def updater(update_getch):

    """
    the game loop spins faster than the updater. So, the server sends a message
    every loop on the update channel, and the updaters only sends the latest
    ones every REFRESH_RATE second, discarding the previous ones
    """

    async def send_updates():
        while True:
            # empty the channel until there is one element left
            while sendch.statistics().current_buffer_used > 1:
                obj = await getch.receive()
                if obj['message']['type'] != 'update':
                    raise ValueError("Removed messages from gameloop-updater "
                                     f"channel of the wrong type {obj}")

            obj = await getch.receive()
            with trio.open_nursery() as n:
                # for c
                pass

            await trio.sleep(REFRESH_RATE)

    return send_updates

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
        n.start_soon(player.get_user_input_forever)

def get_server(player_getch):
    async def server(stream):
        log.info("New connection")

        player = Player(next(PLAYER_COUNT), net.JSONStream(stream))

        try:
            await handle_client(player)
        except net.ConnectionClosed:
            # we couldn't read or we couldn't write
            log.info(f"{player} connection closed")
        except Exception as e:
            log.exception("Handler crashed")
        finally:
            log.info(f"{player} removed")
            del players[player.id]

    return server


# make an average of 10 loops to get the number of loops per second
# when the max_len is going to be reached, items on the left are automatically
# going to be poped left, which is perfect.
loops_times = deque([], maxlen=10)

async def gameloop(nursery, sendch, getch):
    log.info("Start game loop")

    players = {}

    lps = 0
    last = time.time()
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
        loops_times.append(time.time() - last)
        last = time.time()
        lps = sum(loops_times) / len(loops_times)


        async with trio.open_nursery() as n:
            for player in players.values():
                player.send
        await sendch.send({
            "type": "update",
            "players": [p.serializable for p in players.values() if p.is_on_map],
            "lps": lps
        })

async def run():

    async with trio.open_nursery() as nursery:
        Game(nursery)

    return

    # communication for server to gameloop
    player_sendch, player_getch = trio.open_memory_channel(0)
    # communication for gameloop to updater
    update_sendch, udpate_getch = trio.open_memory_channel(0)

    async with trio.open_nursery() as n:
        n.start_soon(trio.serve_tcp, get_server(player_sendch), PORT)
        n.start_soon(gameloop, n, player_sendch, update_sendch)
        n.start_soon(updater(udpate_getch))

