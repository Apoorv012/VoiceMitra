"use client";

import { useEffect, useRef, useState } from "react";

/**
 * WebSocket URL for a backend socket path such as "/ws/patients/<id>/chat".
 *
 * Production (behind the tunnel/reverse proxy) and anything on the page's own origin: same host, since
 * the proxy sends /ws/* to the backend. Next's server does not proxy sockets, so when the page is served
 * by Next itself on :3000 (dev, or `next start`), connect to the backend's port directly.
 */
export function wsUrl(path: string): string {
  const override = process.env.NEXT_PUBLIC_WS_ORIGIN;
  if (override) return `${override}${path}`;
  const { protocol, hostname, port, host } = window.location;
  const scheme = protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${port === "3000" ? `${hostname}:8000` : host}${path}`;
}

/**
 * Keep a socket open to `path` (null = don't connect), calling `onEvent` for every JSON message and
 * reconnecting with backoff. The server sends a fresh snapshot on every connect, so reconnecting needs
 * no extra bookkeeping here. Returns `send` and whether the socket is currently open.
 */
export function useSocket<E>(path: string | null, onEvent: (event: E) => void) {
  const handler = useRef(onEvent);
  const socket = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    handler.current = onEvent;
  });

  useEffect(() => {
    if (!path) return;
    let closed = false;
    let retryMs = 500;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const ws = new WebSocket(wsUrl(path));
      socket.current = ws;
      ws.onopen = () => {
        retryMs = 500;
        setConnected(true);
      };
      ws.onmessage = (ev) => {
        try {
          handler.current(JSON.parse(ev.data));
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (closed) return;
        timer = setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, 10_000);
      };
    };
    connect();

    return () => {
      closed = true;
      clearTimeout(timer);
      socket.current?.close();
      socket.current = null;
      setConnected(false);
    };
  }, [path]);

  const send = (data: unknown) => {
    if (socket.current?.readyState === WebSocket.OPEN) {
      socket.current.send(JSON.stringify(data));
      return true;
    }
    return false;
  };

  return { send, connected };
}
