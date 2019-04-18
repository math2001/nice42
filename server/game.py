import itertools
import logging
import trio
import time
import random
import net
import lockables
from server.player import Player
from collections import deque
from constants import *

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

def read_available(getch):
    """ Read all the available items from a channel"""
    while True:
        try:
            yield getch.receive_nowait()
        except trio.WouldBlock:
            return

class Game:

    def __init__(self, nursery):
        self.players = lockables.Lockable({})

        self.loops_times = deque([], maxlen=10)
        self.lps = 0

        self.last_update = 0

        self.nursery = nursery

        self.nursery.start_soon(trio.serve_tcp, self.accept_players, PORT)
        self.nursery.start_soon(self.gameloop)

        self.notif_sendch, self.notif_getch = trio.open_memory_channel(0)

    async def gameloop(self):
        """ The game loop that checks collisions and stuff """
        log.info("Start game loop")

        last = time.time()
        while True:
            async with self.players.cap_lim:
                for player in self.players.value.values():
                    # gives how long the last loop took, to move accordingly
                    player.move(self.loops_times[-1])

            await self.send_updates()

            # TODO: adjust time based on performances
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

        async with self.players.cap_lim:

            # make sure there aren't duplicate username
            if player.username in self.players.value:
                log.warning(f"Duplicate username: {player.username!r}")
                await player.stream.write({'type': 'close',
                                           'message': "used username"})
                await player.stream.aclose()
                return

        log.info(f"Notification 'new_player' {player}")
        await self.notif_sendch.send({
            'type': 'new_player',
            'player': player
        })

        try:
            await player.get_user_input_forever()
        except net.ConnectionClosed:
            log.info(f"Notification 'gone_players' {player}")
            await self.notif_sendch.send({
                'type': 'gone_players',
                'player': player
            })

    async def send_updates(self):
        """Send updates to the players about the game state

        We can't send data for every frame. Therefore, we only send out every
        SERVER_REFRESH_RATE second.

        An update looks like this:

        {
            # the loops per second that the server makes. It is used to sync
            # the server and the client. It should use absolute time though.
            # (todo)
            "lps": int,
            "players": { username: player.state_for_update(), ...}
            "new_players": { username: player.state_for_initialization(), ...},
            "gone_players": [ player.username, ...]
        }

        """

        if time.time() - self.last_update < SERVER_REFRESH_RATE:
            # normally, we would just "return"
            # but have await trio.sleep(0) guarantees that this function is
            # always a checkpoint, no matter when it is called
            return await trio.sleep(0)

        self.last_update = time.time()

        # this part is a bit tricky
        # To the new players, it sends every existing player and new player as a
        # "new_players", and doesn't say anything about the player that left.
        # To the existing player, it sends new players as "new_player", existing
        # players as "players" and gone players as "gone_players"

        new_players = []
        gone_players = []
        for notif in read_available(self.notif_getch):
            if notif['type'] == 'new_player':
                new_players.append(notif['player'])
            elif notif['type'] == 'gone_players':
                gone_players.append(notif['player'])

        async with self.players.cap_lim:
            new_player_update = {
                "type": "update",
                "lps": self.lps,
                "players": {},
                "gone_players": {},
                "players": {
                    p.username: p.state_for_initialization()
                    for p in itertools.chain(new_players,
                                             self.players.value.values())
                }
            }

            existing_player_update = {
                "type": "update",
                "lps": self.lps,
                "players": {
                    p.username: p.state_for_update()
                    for p in self.players.value.values()
                },
                "gone_players": [p.username for p in gone_players],
                "new_players": {
                    p.username: p.state_for_initialization()
                    for p in new_players
                }
            }

            # add new_players to the existing player list
            for player in new_players:
                log.debug(f"Add new player: {player}")
                self.players.value[player.username] = player

            # remove the gone_players and add the new players
            for player in gone_players:
                log.debug(f"Remove player: {player}")
                del self.players.value[player.username]

            # send updates to all the players
            async with trio.open_nursery() as nursery:
                for player in self.players.value.values():
                    nursery.start_soon(player.stream.write,
                                       existing_player_update)
                for player in new_players:
                    nursery.start_soon(player.stream.write,
                                       new_player_update)
