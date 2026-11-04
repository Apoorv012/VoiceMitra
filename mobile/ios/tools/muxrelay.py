#!/usr/bin/env python3
"""Lets xtool (in WSL) reach the iPhone through Apple's usbmuxd on Windows -- no usbipd, no admin.

Apple Mobile Device Service (installed with iTunes / Apple Devices) listens on Windows 127.0.0.1:27015,
which WSL can't reach in its default (NAT) networking mode. This listens on WSL's 127.0.0.1:27015 and,
for every connection, starts a Windows Python (muxbridge_win.py) that connects to the real service and
pipes bytes both ways.

    python3 muxrelay.py &              # in WSL
    export USBMUXD_SOCKET_ADDRESS=127.0.0.1:27015
    xtool devices

Env: WIN_PYTHON (default /mnt/c/Python314/python.exe), RELAY_PORT (default 27015).
"""
import asyncio
import os
import pathlib

WIN_PYTHON = os.environ.get("WIN_PYTHON", "/mnt/c/Python314/python.exe")
PORT = int(os.environ.get("RELAY_PORT", "27015"))
BRIDGE = pathlib.Path(__file__).with_name("muxbridge_win.py").resolve()


def win_path(p: pathlib.Path) -> str:
    s = str(p)
    if s.startswith("/mnt/") and len(s) > 6:
        return f"{s[5].upper()}:\\" + s[7:].replace("/", "\\")
    return s


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    proc = await asyncio.create_subprocess_exec(
        WIN_PYTHON, "-u", win_path(BRIDGE),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
    )

    async def up() -> None:
        try:
            while data := await reader.read(65536):
                proc.stdin.write(data)
                await proc.stdin.drain()
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    async def down() -> None:
        try:
            while data := await proc.stdout.read(65536):
                writer.write(data)
                await writer.drain()
        finally:
            writer.close()

    t_up = asyncio.create_task(up())
    await down()
    t_up.cancel()
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    await proc.wait()


async def main() -> None:
    server = await asyncio.start_server(handle, "127.0.0.1", PORT)
    print(f"usbmux relay on 127.0.0.1:{PORT} -> Windows 127.0.0.1:27015", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
