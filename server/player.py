import net
import random
from log import getLogger

log = getLogger()

class Player:

    def __init__(self, id, stream):
        self.id = id
        self.name = None
        self.stream = stream
        self.pos = None

        self.color = [
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        ]

        # 0 top, 1 right, 2 bottom and 3 is left
        self.weak_side = random.randint(0, 3)

    async def get_name(self):
        resp = await net.read(self.stream)

        if resp['type'] != 'username':
            raise ValueError(f"invalid response: type should be 'username' in {resp}")

        if 'username' not in resp:
            raise ValueError(f"invalid response: 'username' key should be set in {resp}")

        self.name = resp['username']
        log.info(f"Player got name: {self.name}")

    def spawn(self, pos):
        if self.is_on_map:
            raise RuntimeError("player already spawned")
        self.pos = pos

    async def get_user_input_forever(self):
        while True:
            resp = await net.read(self.stream)

    async def send_player_state_forever(self, players):
        while True:
            net.write(self.stream, {
                "type": "update",
                "players": list(players.values())
            })
            await trio.sleep(REFRESH_RATE)

    @property
    def is_on_map(self):
        return self.pos is not None

    @property
    def get_sendable_info(self):
        return {
            "pos": self.pos,
            "color": self.color
        }