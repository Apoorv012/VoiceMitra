"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, api, toSignIn } from "@/lib/api";

/**
 * A single-use ticket for opening one socket. Sockets go straight to the API host, which never sees this
 * site's sign-in cookie, so the page asks for a ticket (through `/api`, with the cookie) and hands it over.
 */
async function ticket(): Promise<string> {
  const { ticket } = await api<{ ticket: string }>("/api/auth/ws-ticket", { method: "POST" });
  return ticket;
}

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

    const retry = () => {
      timer = setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 2, 10_000);
    };

    const connect = async () => {
      let t: string;
      try {
        t = await ticket();
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return toSignIn();
        if (!closed) retry();
        return;
      }
      if (closed) return;
      const ws = new WebSocket(`${wsUrl(path)}${path.includes("?") ? "&" : "?"}ticket=${encodeURIComponent(t)}`);
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
        retry();
      };
    };
    void connect();

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
