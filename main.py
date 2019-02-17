import sys
import trio

if len(sys.argv) != 2:
    print("Invalid number of arguments")
    print("Usage: $ python main.py <action>")
    print("where <action> is:")
    print(" - server")
    print(" - client")
    exit(2)

if sys.argv[1] == 'server':
    import server
    trio.run(server.run)
elif sys.argv[1] == 'client':
    import client
    trio.run(client.run)