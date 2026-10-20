// Runs the whole stack in this terminal: the API, the web app and (if installed) the tunnel, with
// prefixed, colour-coded logs. Ctrl+C stops all of it. Use through the npm scripts (see README.md):
//
//   npm run dev          web app with hot reload          npm run demo        same, on the demo database
//   npm start            production web app (installable) npm run start:demo  same, on the demo database
//   npm run dev:local / start:local   the same without the tunnel

import concurrently from "concurrently";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const flags = new Set(process.argv.slice(2));
const prod = flags.has("--prod");
const demo = flags.has("--demo");
const wantTunnel = !flags.has("--no-tunnel");

const API_PORT = 8000;
const WEB_PORT = 3000;
const TUNNEL = "voicemitra-test";
const PHONE_URL = "https://test-voicemitra.apoorvm.com";

function fail(message) {
  console.error(`\n  ${message}\n`);
  process.exit(1);
}

// --- preflight: say what's wrong plainly instead of letting three processes fail messily -----------
const python = process.platform === "win32"
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : path.join(root, ".venv", "bin", "python");
if (!existsSync(python)) {
  fail("No .venv found. Create it once:  python -m venv .venv  then  .venv\\Scripts\\activate  and  pip install -r requirements.txt");
}
if (!existsSync(path.join(root, ".env"))) fail("No .env found. Copy .env.example to .env and fill in the API keys.");
if (!existsSync(path.join(root, "web", "node_modules"))) fail("The web app's packages are missing. Run  npm install  in this folder.");

/** True if something already accepts connections on the port (e.g. a server left over from last time). */
const inUse = (port) =>
  new Promise((resolve) => {
    const socket = net.connect({ port, host: "127.0.0.1" });
    socket.once("connect", () => { socket.destroy(); resolve(true); });
    socket.once("error", () => resolve(false));
  });

for (const [port, what] of [[API_PORT, "the API"], [WEB_PORT, "the web app"]]) {
  if (await inUse(port)) {
    fail(`Port ${port} (${what}) is already in use, probably a server from an earlier run.\n  Stop it first, or you'd have two servers fighting over the port.`);
  }
}

// --- the tunnel is optional: without cloudflared you simply have no phone URL --------------------------
function findCloudflared() {
  const probe = spawnSync(process.platform === "win32" ? "where" : "which", ["cloudflared"], { encoding: "utf8" });
  if (probe.status === 0) return "cloudflared";
  const windowsDefault = "C:\\Program Files (x86)\\cloudflared\\cloudflared.exe";
  return existsSync(windowsDefault) ? `"${windowsDefault}"` : null;
}
const cloudflared = wantTunnel ? findCloudflared() : null;

// --- what to run ----------------------------------------------------------------------------------------
const commands = [
  {
    name: "api",
    prefixColor: "cyan",
    // 127.0.0.1 only: the web app and the tunnel both reach it through localhost, so it needn't be on the LAN.
    command: `"${python}" -m uvicorn backend.main:app --host 127.0.0.1 --port ${API_PORT}${prod ? "" : " --reload"}`,
    cwd: root,
    env: demo ? { MONGODB_DB_NAME: "voicemitra_demo" } : {},
  },
  {
    name: "web",
    prefixColor: "magenta",
    command: prod
      ? `npm run build && npm run start -- --port ${WEB_PORT}`
      : `npm run dev -- --port ${WEB_PORT}`,
    cwd: path.join(root, "web"),
  },
];
if (cloudflared) {
  commands.push({
    name: "tunnel",
    prefixColor: "yellow",
    // `|| echo`: a tunnel that can't connect (not logged in, offline) must not take the API and web app down.
    // `--loglevel warn`: cloudflared's startup is ~45 lines of connectivity checks; errors still show.
    command: `${cloudflared} tunnel --loglevel warn run ${TUNNEL} || echo tunnel stopped`,
    cwd: root,
  });
}

console.log(`
  VoiceMitra  ·  ${prod ? "production web app (installable)" : "dev mode (hot reload)"}  ·  ${demo ? "DEMO database (voicemitra_demo)" : "your real database"}
  This computer:  http://localhost:${WEB_PORT}
  Phone:          ${cloudflared ? PHONE_URL : wantTunnel ? "no phone URL: install cloudflared (winget install Cloudflare.cloudflared)" : "tunnel off"}
  Ctrl+C stops everything.${prod ? "\n  The web app builds first, so give it about 30 seconds." : ""}
`);

const { result } = concurrently(commands, {
  prefix: "name",
  killOthersOn: ["failure"], // if the API or web app crashes, stop the rest so it is noticed
  handleInput: false,
});

result.then(
  () => process.exit(0),
  () => process.exit(1),
);
