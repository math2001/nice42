import trio
from logging import getLogger
from server.game import Game

log = getLogger(__name__)

async def run(nursery):
    log.info("Star server")
    Game(nursery)
    log.info("Exiting server")