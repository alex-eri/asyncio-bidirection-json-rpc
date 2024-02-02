import asyncio
import bidirpc

class Server():
    async def echo(self, client, data):
        print('echo', data)
        client.notify('echo_notify', data)
        return data

async def main():
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_connection(
        lambda: bidirpc.RPCProtocol(Server),
        '127.0.0.1', 8888)

    client = await protocol.get_rpc_client()

    print('client.hello', await client.hello())
    print('client.ping', await client.ping())
    try:
        await client.knownerror()
    except Exception as e:
        print('client.error', repr(e))
    
    try:
        await client.unknownerror()
    except Exception as e:
        print('client.error.name', e.__name__)
        print('client.error', repr(e))

asyncio.run(main())