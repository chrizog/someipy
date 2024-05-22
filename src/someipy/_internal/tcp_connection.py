import asyncio
from someipy._internal.logging import get_logger

_logger_name = "tcp_connection"

class TcpConnection():
    def __init__(self, ip_server: str, port: int):
        self.ip_server = ip_server
        self.port = port
        self.reader = None
        self.writer = None

    async def connect(self, src_ip: str, src_port: int):
        try:
            local_addr = (src_ip, src_port)
            self.reader, self.writer = await asyncio.open_connection(self.ip_server, self.port, local_addr=local_addr)
            get_logger(_logger_name).debug(f"Connected to {self.ip_server}:{self.port}")
        except Exception as e:
            get_logger(_logger_name).error(f"Error connecting to {self.ip_server}:{self.port}: {e}")

    def is_open(self):
        if self.writer is None or self.writer.is_closing():
            return False
        return not self.reader.at_eof()
    
    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.writer = None
            get_logger(_logger_name).debug(f"Connection to {self.ip_server}:{self.port} closed")
        else:
            get_logger(_logger_name).debug("No connection to close")