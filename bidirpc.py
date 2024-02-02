import asyncio
from typing import Any
import functools
import itertools
import msgpack
import builtins

class UnnownException(Exception):
    def __init__(self, *a, __name__='UnnownException'):
        super().__init__(*a)
        self.__name__ = __name__

    def __repr__(self) -> str:
        return f'{self.__name__}<UnnownException>({", ".join(repr(a) for a in self.args)})'


class Server():
    async def ping(self, client, *a, **kw):
        return 204

class Client():
    def __init__(self, protocol):
        self.protocol = protocol

    def __getattribute__(self, __name: str) -> Any:
        if __name in ["notify", "call", "protocol", "__call__"]:
            return super().__getattribute__(__name)
        return functools.partial(self, __name)

    def __call__(self, method, *args, **params):
        return self.call(method, *args, **params)

    async def call(self, method, *args, **params):
        return await (self.protocol).call_run(method,args,params)

    def notify(self, method, *args, **params):
        return self.protocol.notify_run(method,args,params)


class RPCProtocol(asyncio.Protocol):
    def __init__(self, server=Server, knownerrors=[builtins]):
        self._server = server()
        self._head = b''
        self._results = {}
        self._client = asyncio.Future()
        self._client_factory = Client
        self._id = itertools.count(1)
        self.unpacker = msgpack.Unpacker()
        self.knownerrors = knownerrors

    def get_rpc_client(self):
        return self._client

    def connection_made(self, transport):
        self.transport = transport
        self._client.set_result(self._client_factory(self))


    def data_received(self, data):
        self.unpacker.feed(data)
        for message in self.unpacker:
            asyncio.create_task(self.process(message))
        
    async def process(self, message):
        match message['type']:
            case 'call'|'notify':
                try:
                    result = getattr(self._server, message['method'])(
                        (await self._client),
                        *message.get('args',[]),
                        **message.get('params', {})
                    )
                    if asyncio.iscoroutine(result):
                        result = await result
                    if message['type'] == 'call':
                        self.return_send(result, message['id'])
                except Exception as e:
                    self.error_send(e, message['id'])
            
            case 'return':
                self._results[message['id']].set_result(message['result'])
            
            case 'error':
                for module in self.knownerrors:
                    if hasattr(module, message['exception'][0]):
                        typ = getattr(module, message['exception'][0])
                        if issubclass(typ, BaseException):
                            e = typ(*message['exception'][1])
                            break
                else:
                    e = UnnownException(*message['exception'][1], __name__=message['exception'][0])
                self._results[message['id']].set_exception(e)


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

    def error_send(self, e, _id):
        message = {'type':'error','exception': (type(e).__name__, e.args), 'id':_id}
        self.message_send(message)

    def message_send(self, message):
        data = msgpack.packb(message)
        self.transport.write(data)

