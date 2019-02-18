import trio
import time
import random
import net
from server.player import Player
from log import getLogger
from itertools import count
from collections import deque
from constants import *
from server.constants import *

log = getLogger('DEBUG')

class Game:

    def __init__(self, nursery):
        self.players = {}
        self.players_semaphore = trio.Semaphore(1)

        self.player_counter = count()

        self.loops_times = deque([], maxlen=10)
        self.lps = 0

        self.last_update = 0

        self.nursery = nursery

        self.nursery.start_soon(trio.serve_tcp, self.accept_players, PORT)
        nursery.start_soon(self.gameloop)

    async def gameloop(self):
        """ The game loop that checks collisions and stuff """
        log.info("Start game loop")

        last = time.time()
        while True:
            await self.players_semaphore.acquire()
            for player in self.players.values():
                player.move()

                # check collision
                for target in self.players.values():
                    if target is player:
                        continue
                    if player.collides(target):
                        if random.randint(0, 1) == 0:
                            self.player_dead(player)
                        else:
                            self.player_dead(target)

            # should I release players_semaphore to relock again in the function
            # or keep it this way? is it that expensive to lock/unlock
            await self.send_updates()

            self.players_semaphore.release()

            await trio.sleep(.01)
            self.loops_times.append(time.time() - last)
            last = time.time()
            self.lps = round(sum(self.loops_times) / len(self.loops_times) * 1000, 2)

    async def accept_players(self, stream):
        """ Accepts players and puts them into self.players once
        they are ready for the game loop """
        log.info("New connection")

        player = Player(next(self.player_counter), net.JSONStream(stream))

        try:
            await self.initiate_player(player)
        except net.ConnectionClosed:
            log.info(f"{player} connection closed")
        except Exception as e:
            log.exception("Initiater crashed")
        else:
            await self.players_semaphore.acquire()
            self.players[player.id] = player
            self.players_semaphore.release()

        await player.get_user_input_forever()

    async def initiate_player(self, player):
        log.debug("Waiting for player's name")
        await player.get_name()
        player.spawn((
            random.randint(0, MAP_SIZE[0] - PLAYER_SIZE[0]),
            random.randint(0, MAP_SIZE[1] - PLAYER_SIZE[1]),
        ))
        log.info(f"{player} added to players dict")

    async def send_updates(self):
        """Send updates to the players about the game state

        Unfortunartely, we can't send data for every frame. Therefore, we only
        send out every REFRESH_RATE second.
        """

        # note that this assumes that self.players_semaphore is acquired

        # TODO: optimise communication (stateful)

        if time.time() - self.last_update < REFRESH_RATE:
            return
        log.debug(f"Send updates to {len(self.players)} clients")

        self.last_update = time.time()

        players = [p.serializable for p in self.players.values() if p.is_on_map]

        # async with trio.open_nursery() as nursery:
        #     for player in self.players.values():
        #         # should I make wrapper as player.write that would do
        #         # player.stream.write?
        #         nursery.start_soon(player.stream.write, {
        #             'type': 'update',
        #             'players': players,
        #             'lps': self.lps,
        #         })

        for player in self.players.values():
            # should I make wrapper as player.write that would do
            # player.stream.write?
            await player.stream.write({
                'type': 'update',
                'players': players,
                'lps': self.lps,
            })