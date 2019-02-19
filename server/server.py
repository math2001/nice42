import trio
from log import getLogger
from server.game import Game

log = getLogger()

async def run():
    log.info("Star server")
    async with trio.open_nursery() as nursery:
        Game(nursery)
    log.info("Exiting server")