// Runs the whole stack in this terminal: the API, the web app and (if installed) the tunnel, with
// prefixed, colour-coded logs. Ctrl+C stops all of it. Use through the npm scripts (see README.md):
//
//   npm run dev        the web app as a production build (fast pages, the installable app works)
//   npm run demo       the same on the demo database
//   npm run dev:local  the same without the tunnel
//
// Flags go after npm's `--`:   npm run dev -- --hot
//   --hot       run the web app with hot reload (`next dev`), for when you are editing the frontend.
//               Slower to load: it compiles pages on demand. The HOT=1 environment variable does the same.
//   --rebuild   build the web app even if nothing has changed since the last build.
// (`npm run dev:hot` and `npm run demo:hot` are shortcuts for the --hot forms.)

import concurrently from "concurrently";
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, statSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const flags = new Set(process.argv.slice(2));
const isSet = (value) => value !== undefined && !["", "0", "false", "no"].includes(String(value).toLowerCase());
const hot = flags.has("--hot") || isSet(process.env.HOT);
const rebuild = flags.has("--rebuild");
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

// --- build the web app only when something changed -------------------------------------------------------
// `next build` is the slow part of a start; if the last build is newer than every source file, reuse it.
function newestChange(paths) {
  let newest = 0;
  const walk = (p) => {
    let info;
    try { info = statSync(p); } catch { return; }
    if (info.isDirectory()) readdirSync(p).forEach((name) => walk(path.join(p, name)));
    else newest = Math.max(newest, info.mtimeMs);
  };
  paths.forEach(walk);
  return newest;
}

function needsBuild() {
  const marker = path.join(root, "web", ".next", "BUILD_ID"); // written by `next build`, never by `next dev`
  if (rebuild || !existsSync(marker)) return true;
  const inputs = ["src", "public", "next.config.ts", "package.json", "tsconfig.json", "openapi.json"];
  return newestChange(inputs.map((p) => path.join(root, "web", p))) > statSync(marker).mtimeMs;
}

const building = !hot && needsBuild();
const webMode = hot ? "hot reload (next dev)" : building ? "production build (building first)" : "production build (up to date, not rebuilding)";

// --- what to run ----------------------------------------------------------------------------------------
const commands = [
  {
    name: "api",
    prefixColor: "cyan",
    // 127.0.0.1 only: the web app and the tunnel both reach it through localhost, so it needn't be on the LAN.
    command: `"${python}" -m uvicorn backend.main:app --host 127.0.0.1 --port ${API_PORT} --reload`,
    cwd: root,
    env: demo ? { MONGODB_DB_NAME: "voicemitra_demo" } : {},
  },
  {
    name: "web",
    prefixColor: "magenta",
    command: hot
      ? `npm run dev -- --port ${WEB_PORT}`
      : `${building ? "npm run build && " : ""}npm run start -- --port ${WEB_PORT}`,
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
  VoiceMitra  ·  web app: ${webMode}  ·  ${demo ? "DEMO database (voicemitra_demo)" : "your real database"}
  This computer:  http://localhost:${WEB_PORT}
  Phone:          ${cloudflared ? PHONE_URL : wantTunnel ? "no phone URL: install cloudflared (winget install Cloudflare.cloudflared)" : "tunnel off"}
  Ctrl+C stops everything.${building ? "\n  Building the web app first (usually 10-30 seconds)." : ""}
  ${hot ? "Hot reload is slower to load pages. Drop --hot for the built app." : "Editing the frontend? Add --hot for hot reload:  npm run dev -- --hot"}
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
