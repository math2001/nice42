import trio
import random
import logging
from itertools import count

players = {}

PLAYER_COUNT = count()

async def handle_client(stream):
    await player.get_name()
    player.spawn(
        random.randint(0, MAP_SIZE - PLAYER_SIZE),
        random.randint(0, MAP_SIZE - PLAYER_SIZE),
    )
    with trio.open_nursery() as n:
        n.start_soon(player.get_user_input_forever())
        n.start_soon(player.send_player_state_forever())

async def server(stream):
    log.info("New connection")

    player = Player(next(count), stream)
    players[id] = player

    try:
        await handle_client(stream)
    except Exception as e:
        log.exception("Handler crashed")
        del players[player.id]

async def gameloop(nursery):
    while True:
        for player in players.values():
            # if 2 player collide, one of them has to die
            # keep shit simple for now. Random'll do
            for target in players.values():
                if player.collides(target):
                    if random.randint(0, 1) == 0:
                        n.start_soon(player.dead())
                    else:
                        n.start_soon(target.dead())


        await trio.sleep(0)

async def main():
    with trio.open_nursery() as n:
        n.start_soon(trio.serve_tcp, server, PORT)
        n.start_soon(gameloop, n)

if __name__ == "__main__":
    trio.run(main)