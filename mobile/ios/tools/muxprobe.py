#!/usr/bin/env python3
"""Asks usbmuxd (via USBMUXD_SOCKET_ADDRESS, default 127.0.0.1:27015) for the connected devices."""
import os
import plistlib
import socket
import struct

host, port = os.environ.get("USBMUXD_SOCKET_ADDRESS", "127.0.0.1:27015").rsplit(":", 1)
body = plistlib.dumps({"MessageType": "ListDevices", "ClientVersionString": "muxprobe",
                       "ProgName": "muxprobe", "kLibUSBMuxVersion": 3})
s = socket.create_connection((host, int(port)), timeout=10)
s.sendall(struct.pack("<IIII", 16 + len(body), 1, 8, 1) + body)
hdr = b""
while len(hdr) < 16:
    hdr += s.recv(16 - len(hdr))
length = struct.unpack("<IIII", hdr)[0]
data = b""
while len(data) < length - 16:
    data += s.recv(length - 16 - len(data))
devices = plistlib.loads(data).get("DeviceList", [])
print(f"{len(devices)} device(s)")
for d in devices:
    p = d.get("Properties", {})
    print(" ", p.get("ConnectionType"), p.get("SerialNumber") or p.get("UDID"), p.get("ProductID"))
