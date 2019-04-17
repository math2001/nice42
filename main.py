import sys
import trio
import logging

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(name)-15s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG
)

if len(sys.argv) != 2:
    print("Invalid number of arguments")
    print("Usage: $ python main.py <action> <debug port>")
    print("where <action> is:")
    print(" - server")
    print(" - client")
    exit(2)

def main():
    if sys.argv[1] == 'server':
        import server
        trio.run(server.run)
    elif sys.argv[1] == 'client':
        import client
        trio.run(client.run)
    else:
        print(f"Invalid command {sys.argv[1]}")
        exit(1)

try:
    main()
except KeyboardInterrupt:
    print("Bye")