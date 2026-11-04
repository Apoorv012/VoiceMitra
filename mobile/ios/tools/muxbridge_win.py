"""Windows side of the usbmux relay: pipes stdin/stdout to Apple's usbmuxd on 127.0.0.1:27015.

Started once per connection by muxrelay.py (inside WSL), through WSL's Windows interop.
"""
import msvcrt
import os
import socket
import threading

for fd in (0, 1):
    msvcrt.setmode(fd, os.O_BINARY)
sock = socket.create_connection(("127.0.0.1", 27015))


def pump_in() -> None:
    while True:
        data = os.read(0, 65536)
        if not data:
            break
        sock.sendall(data)
    try:
        sock.shutdown(socket.SHUT_WR)
    except OSError:
        pass


threading.Thread(target=pump_in, daemon=True).start()
while True:
    try:
        data = sock.recv(65536)
    except OSError:
        break
    if not data:
        break
    while data:
        n = os.write(1, data)
        data = data[n:]
