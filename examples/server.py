import asyncio
import bidirpc

class ServerUnknownError(Exception):
    pass

class Server(bidirpc.Server):
    async def hello(self, client, *a, **kw):
        print('hello', a, kw)
        r = await client.echo('hello')
        return 'hellohello'

    def echo_notify(self, client, data):
        print('echo_notify', data)

    def knownerror(self, client):
        raise AssertionError('hello')

    def unknownerror(self, client):
        raise ServerUnknownError('^')

async def main():
    loop = asyncio.get_running_loop()
    server = await loop.create_server(
        lambda: bidirpc.RPCProtocol(Server),
        '127.0.0.1', 8888)

    async with server:
        await server.serve_forever()


asyncio.run(main())