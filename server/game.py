import logging
import trio
import time
import random
import net
from server.player import Player
from collections import deque
from constants import *

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class Game:

    def __init__(self, nursery):
        self.players = {}
        self.players_semaphore = trio.Semaphore(1)

        self.loops_times = deque([], maxlen=10)
        self.lps = 0

        self.last_update = 0

        self.nursery = nursery

        self.nursery.start_soon(trio.serve_tcp, self.accept_players, PORT)
        self.nursery.start_soon(self.gameloop)

        self.new_player_sendch, self.new_player_getch = trio.open_memory_channel(0)

    async def gameloop(self):
        """ The game loop that checks collisions and stuff """
        log.info("Start game loop")

        last = time.time()
        while True:
            async with self.players_semaphore:
                for player in self.players.values():
                    # gives how long the last loop took, to move accordingly
                    player.move(self.loops_times[-1])

                    # check collision
                    for target in self.players.values():
                        if target is player:
                            continue
                        if player.collides(target):
                            if random.randint(0, 1) == 0:
                                self.player_dead(player)
                            else:
                                self.player_dead(target)

            await self.send_updates()

            await trio.sleep(.01)
            self.loops_times.append(time.time() - last)
            last = time.time()
            self.lps = int(round(sum(self.loops_times) / len(self.loops_times) * 1000))

    async def accept_players(self, stream):
        """ Accepts players and puts them into self.players once
        they are ready for the game loop """
        log.info("New connection")

        player = Player(net.JSONStream(stream))

        try:
            log.debug("Waiting for player name")
            await player.get_username()
        except net.ConnectionClosed:
            log.info(f"{player} connection closed")
        except Exception as e:
            log.exception("Initiater crashed")
        else:
            log.info(f"Add {player} to players dict")
            player.spawn((
                random.randint(0, MAP_SIZE[0] - PLAYER_SIZE[0]),
                random.randint(0, MAP_SIZE[1] - PLAYER_SIZE[1]),
            ))

            await self.new_player_sendch.send(player)

            try:
                await player.get_user_input_forever()
            except net.ConnectionClosed:
                log.info(f"{player} connection closed")
                async with self.players_semaphore:
                    del self.players[player.username]

    async def send_updates(self):
        """Send updates to the players about the game state

        Unfortunartely, we can't send data for every frame. Therefore, we only
        send out every SERVER_REFRESH_RATE second.
        """

        # note that this assumes that self.players_semaphore is acquired

        # TODO: optimise communication (stateful)

        if time.time() - self.last_update < SERVER_REFRESH_RATE:
            return await trio.sleep(0) # guaranty that this function is checkpoint

        self.last_update = time.time()

        players = {
            p.username: {'pos': p.pos} for p in self.players.values() if p.is_on_map
        }

        new_players = {}
        has_new_players = True
        while has_new_players:
            try:
                new = self.new_player_getch.receive_nowait()
            except trio.WouldBlock: # queue is empty
                has_new_players = False
            else:
                new_players[new.username] = {
                    'pos': new.pos,
                    'color': new.color,
                }

                async with self.players_semaphore:
                    self.players[new.username] = new

        # don't add 'new' key if new == []?
        obj = {
            'type': 'update',
            'players': players,
            'new': new_players,
            'lps': self.lps
        }

        log.debug(f"Sending to {len(self.players)} players: {obj}")

        # put this in a nursery to .start_soon instead of await?
        # how long can a .write hang for?
        for player in self.players.values():
            # should I make wrapper as player.write that would do
            # player.stream.write?
            await player.stream.write(obj)