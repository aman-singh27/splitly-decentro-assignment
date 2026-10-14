/** Dedicated E2E database/media isolate browser journeys from developer data. */
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const venv = path.join(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const python =
  process.env.E2E_PYTHON ||
  (existsSync(venv)
    ? venv
    : process.platform === "win32"
      ? "python"
      : "python3");
const env = {
  ...process.env,
  DJANGO_DEBUG: "true",
  SQLITE_PATH: path.join(root, ".e2e.sqlite3"),
  MEDIA_ROOT: path.join(root, ".e2e-media"),
  DJANGO_CSRF_TRUSTED_ORIGINS: "http://127.0.0.1:5173",
};
const migration = spawnSync(python, ["manage.py", "migrate", "--noinput"], {
  cwd: root,
  env,
  stdio: "inherit",
});
if (migration.status !== 0) process.exit(migration.status || 1);
const server = spawn(
  python,
  ["manage.py", "runserver", "127.0.0.1:8001", "--noreload"],
  { cwd: root, env, stdio: "inherit" },
);
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => server.kill(signal));
server.on("exit", (code) => process.exit(code || 0));
