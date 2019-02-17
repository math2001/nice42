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

        self.dead = False
        self.speed = 1
        self.keyboard_state = 0

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
            if resp['type'] != 'keyboard':
                raise ValueError(f"Expected type='keyboard' in {resp}")
            self.keyboard_state = resp['state']

    async def send_player_state_forever(self, players):
        while True:
            if self.dead:
                # gross, but stops the nursery and all
                # TODO: improve this
                raise ValueError("I'm dead!")
            await net.write(self.stream, {
                "type": "players",
                "players": list(p for p in players.values() if p.is_on_map)
            })
            await trio.sleep(REFRESH_RATE)

    async def dead(self):
        await net.write(self.stream, {
            "type": "dead"
        })
        self.dead = True

    def move(self):
        """ Move according to the keyboard state """
        if self.keyboard_state & LEFT:
            self.pos[0] -= 1
        if self.keyboard_state & RIGHT:
            self.pos[0] += 1
        if self.keyboard_state & UP:
            self.pos[1] -= 1
        if self.keyboard_state & DOWN:
            self.pos[1] += 1

    @property
    def is_on_map(self):
        return self.pos is not None

    @property
    def get_sendable_info(self):
        return {
            "pos": self.pos,
            "color": self.color
        }