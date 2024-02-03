import asyncio
from typing import Any
import functools
import itertools
import msgpack
import builtins

from enum import IntEnum, auto

class Pk(IntEnum):
    TYPE = auto()
    PING = auto()
    PONG = auto()
    CALL = auto()
    NOTIFY = auto()
    ARGS = auto()
    PARAMS = auto()
    METHOD = auto()
    ID = auto()
    RETURN = auto()
    RESULT = auto()
    ERROR = auto()
    EXCEPTION = auto()


class UnnownException(Exception):
    def __init__(self, *a, __name__='UnnownException'):
        super().__init__(*a)
        self.__name__ = __name__

    def __repr__(self) -> str:
        return f'{self.__name__}<UnnownException>({", ".join(repr(a) for a in self.args)})'


class Server():
    async def generate_204(self, client, *a, **kw):
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
    def __init__(self, server=Server, knownerrors=[builtins], keepalive=10):
        self._server = server()
        self._head = b''
        self._results = {}
        self._client = asyncio.Future()
        self._client_factory = Client
        self._id = itertools.count(1)
        self.unpacker = msgpack.Unpacker(strict_map_key=False)
        self.knownerrors = knownerrors
        self.keepalive = keepalive


    def get_rpc_client(self):
        return self._client

    def ping_send(self):
        if self.keepalive:
            self.message_send({Pk.TYPE:Pk.PING})
            self.keepalive_timer = asyncio.get_running_loop().call_later(
                self.keepalive, 
                self.ping_send
            )

    def connection_made(self, transport):
        self.transport = transport
        self._client.set_result(self._client_factory(self))
        self.ping_send()

    def data_received(self, data):
        self.unpacker.feed(data)
        for message in self.unpacker:
            asyncio.create_task(self.process(message))
        
    async def process(self, message):
        match message[Pk.TYPE]:
            case Pk.CALL|Pk.NOTIFY:
                try:
                    result = getattr(self._server, message[Pk.METHOD])(
                        (await self._client),
                        *message.get(Pk.ARGS,[]),
                        **message.get(Pk.PARAMS, {})
                    )
                    if asyncio.iscoroutine(result):
                        result = await result
                    if message[Pk.TYPE] == Pk.CALL:
                        self.return_send(result, message[Pk.ID])
                except Exception as e:
                    self.error_send(e, message[Pk.ID])
            
            case Pk.RETURN:
                self._results[message[Pk.ID]].set_result(message[Pk.RESULT])
            
            case Pk.ERROR:
                for module in self.knownerrors:
                    if hasattr(module, message[Pk.EXCEPTION][0]):
                        typ = getattr(module, message[Pk.EXCEPTION][0])
                        if issubclass(typ, BaseException):
                            e = typ(*message[Pk.EXCEPTION][1])
                            break
                else:
                    e = UnnownException(*message[Pk.EXCEPTION][1], __name__=message[Pk.EXCEPTION][0])
                self._results[message[Pk.ID]].set_exception(e)
            
            case Pk.PING:
                self.message_send({
                    Pk.TYPE: Pk.PONG
                })
            case Pk.PONG:
                pass


    def notify_run(self, method, args, params):
        result = asyncio.Future()
        message = {
            Pk.TYPE: Pk.NOTIFY,
            Pk.METHOD: method,
            Pk.ARGS: args,
            Pk.PARAMS: params,
        }
        self.message_send(message)
        return result       

    def call_run(self, method, args, params):
        result = asyncio.Future()
        message = {
            Pk.TYPE: Pk.CALL,
            Pk.METHOD: method,
            Pk.ARGS: args,
            Pk.PARAMS: params,
            Pk.ID: next(self._id)
        }
        self._results[message[Pk.ID]] = result
        self.message_send(message)
        return result

    def return_send(self, result, _id):
        message = {Pk.TYPE:Pk.RETURN,Pk.RESULT: result, Pk.ID:_id}
        self.message_send(message)

    def error_send(self, e, _id):
        message = {Pk.TYPE:Pk.ERROR,Pk.EXCEPTION: (type(e).__name__, e.args), Pk.ID:_id}
        self.message_send(message)

    def message_send(self, message):
        data = msgpack.packb(message)
        self.transport.write(data)

