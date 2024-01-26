import asyncio
import bidirpc

class Server():
    async def echo(self, client, data):
        print('echo', data)
        client.notify('echo_notify', data)
        return data

async def main():
    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()

    transport, protocol = await loop.create_connection(
        lambda: bidirpc.RPCProtocol(Server),
        '127.0.0.1', 8888)

    client = await protocol.get_rpc_client()

    print('client.hello', await client.hello())


asyncio.run(main())