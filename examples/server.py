import asyncio
import bidirpc


class Server(bidirpc.Server):
    async def hello(self, client, *a, **kw):
        print('hello', a, kw)
        r = await client.echo('hello')
        return 'hellohello'

    def echo_notify(self,client,data):
        print('echo_notify', data)

async def main():
    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()

    rpcserver = Server

    server = await loop.create_server(
        lambda: bidirpc.RPCProtocol(rpcserver),
        '127.0.0.1', 8888)

    async with server:
        await server.serve_forever()


asyncio.run(main())