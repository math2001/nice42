import logging
import trio
import time
import random
import net
from server.player import Player
from collections import deque
from constants import *

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class Game:

    def __init__(self, nursery):
        # TODO: use lockable!!!!
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
            await self.initiate_player(player)

    async def initiate_player(self, player):
        log.info(f"Initiating new player {player}")
        player.spawn((
            random.randint(0, MAP_SIZE[0] - PLAYER_SIZE[0]),
            random.randint(0, MAP_SIZE[1] - PLAYER_SIZE[1]),
        ))

        async with self.players_semaphore:
            if player.username in self.players:
                log.warning(f"Duplicate username: {player.username!r}")
                await player.stream.write({'type': 'close',
                                           'message': "used username"})
                await player.stream.aclose()
                return

            log.debug(f"Sending 'init game' message to {player}")
            # send current game state to the new player
            await player.stream.write({
                'type': 'init game',
                'players': [],
                'new_players': {p.username: p.state_for_initialization() \
                                for p in self.players.values() if p.is_on_map}
            })

        log.info(f"Add new player {player}")
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
            # guaranties that this function is always a checkpoint
            return await trio.sleep(0)

        self.last_update = time.time()

        # get new players from channel into a dict
        new_players = {}
        has_new_players = True
        while has_new_players:
            try:
                new_player = self.new_player_getch.receive_nowait()
            except trio.WouldBlock: # queue is empty
                has_new_players = False
            else:
                new_players[new_player.username] = new_player

        log.debug(f"Now aware of {len(new_players)} new players")

        # create update object (players, new_players, lps, etc)

        # don't add 'new' key if new == []? Bad for consistency, better for
        # network perfs
        async with self.players_semaphore:
            obj = {
                'type': 'update',
                'players': {p.username: p.state_for_update() \
                            for p in self.players.values() if p.is_on_map},
                'new_players': {p.username: p.state_for_initialization() \
                                for p in new_players.values()},
                'lps': self.lps
            }

            # add new players to the player dict
            for username, player in new_players.items():
                self.players[username] = player

            # send update message to every player
            log.debug(f"Sending to {len(self.players)} players: {obj}")

            # put this in a nursery to .start_soon instead of await?
            # how long can a .write hang for?
            for player in self.players.values():
                # should I make wrapper as player.write that would do
                # player.stream.write?
                await player.stream.write(obj)