import asyncio
import json
from typing import Any
TERMINATOR = b'\0'
import functools
import itertools

class Server():
    pass
    # def echo(self, client, *args, **params):
    #     return params

class Client():
    def __init__(self,protocol):
        self.protocol = protocol

    def __getattribute__(self, __name: str) -> Any:
        if __name in ["notify","call","protocol"]:
            return super().__getattribute__(__name)
        return functools.partial(self, __name)

    def __call__(self, method, *args, **params):
        return self.call(method, *args, **params)

    async def call(self, method, *args, **params):
        return await (self.protocol).call_run(method,args,params)

    def notify(self, method, *args, **params):
        return self.protocol.notify_run(method,args,params)



class RPCProtocol(asyncio.Protocol):
    def __init__(self, server=Server, dumps=json.dumps, loads=json.loads, terminator=TERMINATOR):
        self.dumps = dumps
        self.loads = loads
        self.terminator = terminator
        self._server = server()
        self._head = b''
        self._results = {}
        self._client = asyncio.Future()
        self._client_factory = Client
        self._id = itertools.count(1)
    

    def get_rpc_client(self):
        return self._client

    def connection_made(self, transport):
        self.transport = transport
        self._client.set_result(self._client_factory(self))


    def data_received(self, data):
        self._head += data
        datas = self._head.split(self.terminator)
        self._head = datas[-1]
        for d in datas[:-1]:
            message = self.loads(d)
            asyncio.create_task(self.process(message))
        
    async def process(self, message):
        if message['type'] in ['call', 'notify']:
            result = getattr(self._server, message['method'])(
                (await self._client),
                *message.get('args',[]),
                **message.get('params', {})
            )
            if asyncio.iscoroutine(result):
                result = await result
            if message['type'] == 'call':
                self.return_send(result, message['id'])
            return
        if message['type'] == 'return':
            self._results[message['id']].set_result(message['result'])

    def notify_run(self, method, args, params):
        result = asyncio.Future()
        message = {
            'type': 'notify',
            'method': method,
            'args': args,
            'params': params,
        }
        self.message_send(message)
        return result       


    def call_run(self, method, args, params):
        result = asyncio.Future()
        message = {
            'type': 'call',
            'method': method,
            'args': args,
            'params': params,
            'id': next(self._id)
        }
        self._results[message['id']] = result
        self.message_send(message)
        return result



    def return_send(self, result, _id):
        message = {'type':'return','result': result, 'id':_id}
        self.message_send(message)

    def message_send(self, message):
        data = self.dumps(message)
        if type(data) == str:
            data = data.encode()
        self.transport.write(data)
        self.transport.write(self.terminator)

