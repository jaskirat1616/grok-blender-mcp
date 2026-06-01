"""
Robust TCP connection to the Grok Blender MCP addon running inside Blender.
"""

from __future__ import annotations
import json
import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9876
DEFAULT_TIMEOUT = 180.0


@dataclass
class BlenderConnection:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    sock: Optional[socket.socket] = field(default=None, repr=False)
    connected: bool = False

    def connect(self) -> bool:
        if self.sock and self.connected:
            return True
        try:
            if self.sock:
                try: self.sock.close()
                except Exception: pass
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(DEFAULT_TIMEOUT)
            self.connected = True
            logger.info(f"Connected to Blender at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Blender: {e}")
            self.sock = None
            self.connected = False
            return False

    def disconnect(self) -> None:
        self.connected = False
        if self.sock:
            try: self.sock.close()
            except Exception: pass
            self.sock = None

    def _recv_full(self) -> bytes:
        if not self.sock:
            raise ConnectionError("Not connected")
        chunks: list[bytes] = []
        self.sock.settimeout(DEFAULT_TIMEOUT)
        while True:
            try:
                chunk = self.sock.recv(8192)
                if not chunk:
                    break
                chunks.append(chunk)
                try:
                    data = b"".join(chunks)
                    json.loads(data.decode("utf-8"))
                    return data
                except json.JSONDecodeError:
                    continue
            except socket.timeout:
                break
            except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                self.connected = False
                raise
        if chunks:
            data = b"".join(chunks)
            json.loads(data.decode("utf-8"))
            return data
        raise Exception("No valid response from Blender")

    def send_command(self, command_type: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.connected or not self.sock:
            if not self.connect():
                raise ConnectionError(f"Cannot connect to Blender MCP addon on {self.host}:{self.port}")
        command = {"type": command_type, "params": params or {}}
        try:
            self.sock.sendall(json.dumps(command).encode("utf-8"))
            response_data = self._recv_full()
            response = json.loads(response_data.decode("utf-8"))
            if response.get("status") == "error":
                raise Exception(response.get("message", "Unknown Blender error"))
            return response.get("result", {})
        except Exception as e:
            self.connected = False
            self.sock = None
            raise

    def __enter__(self): self.connect(); return self
    def __exit__(self, *a): self.disconnect()


_blender_connection: Optional[BlenderConnection] = None

def get_blender_connection(host: Optional[str] = None, port: Optional[int] = None, force: bool = False) -> BlenderConnection:
    global _blender_connection
    if _blender_connection is None or force:
        _blender_connection = BlenderConnection(host or DEFAULT_HOST, port or DEFAULT_PORT)
    if not _blender_connection.connected:
        _blender_connection.connect()
    return _blender_connection

def reset_connection():
    global _blender_connection
    if _blender_connection:
        _blender_connection.disconnect()
    _blender_connection = None
