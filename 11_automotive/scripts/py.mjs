// 가상환경의 python 을 운영체제에 맞게 찾아 실행한다 (Windows: .venv\Scripts\python.exe, macOS·Linux: .venv/bin/python)
// npm 스크립트는 Windows에서 cmd.exe 로 돌아 ".venv/Scripts/python" 경로를 못 읽으므로 이걸 거친다.
//   node scripts/py.mjs api          백엔드 API 개발 서버 (:8000, --reload). 환경 파일 = MOM_ENV_FILE (기본 .env.supabase)
//   node scripts/py.mjs sim          시연 데이터 서버 frontend/tools/sim_server.py (:8765, 데이터생성기/.venv 로 실행)
//   node scripts/py.mjs @gen ...     데이터생성기/.venv 의 python 에 인자를 그대로 넘김 (작업 폴더 = 생성기)
//   node scripts/py.mjs ...          backend/.venv 의 python 에 인자를 그대로 넘김 (작업 폴더 = backend)
// (Node 24는 스크립트 뒤 인자의 --env-file 까지 자기 옵션으로 읽으므로 uvicorn 의 --env-file 은 여기서 붙인다)
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");   // 11_automotive
const VENVS = {
  backend: { dir: join(root, "backend"), setup: "npm run setup:api" },
  gen: { dir: join(root, "데이터생성기"), setup: "npm run setup:sim  (데이터생성기/실행_안내.md)" },
};

function venvPython(name) {
  const { dir, setup } = VENVS[name];
  const python = process.platform === "win32"
    ? join(dir, ".venv", "Scripts", "python.exe")
    : join(dir, ".venv", "bin", "python");
  if (!existsSync(python)) {
    console.error(`가상환경이 없음: ${python}\n먼저 11_automotive 에서 ${setup}`);
    process.exit(1);
  }
  return python;
}

let args = process.argv.slice(2);
let python, cwd;
const env = { ...process.env };

if (args[0] === "api") {
  python = venvPython("backend");
  cwd = VENVS.backend.dir;
  const envFile = process.env.MOM_ENV_FILE || ".env.supabase";
  if (!existsSync(join(cwd, envFile))) {
    console.error(`환경 파일이 없음: backend/${envFile}\n${envFile}.example 을 복사해 값을 채운다 (Docker DB면 MOM_ENV_FILE=.env)`);
    process.exit(1);
  }
  args = ["-m", "uvicorn", "app.main:app", "--env-file", envFile, "--reload", "--port", "8000", ...args.slice(1)];
} else if (args[0] === "sim") {
  python = venvPython("gen");
  cwd = join(root, "frontend");
  env.PYTHONIOENCODING = "utf-8";
  args = [join("tools", "sim_server.py"), ...args.slice(1)];
} else if (args[0] === "@gen") {
  python = venvPython("gen");
  cwd = VENVS.gen.dir;
  args = args.slice(1);
} else {
  python = venvPython("backend");
  cwd = VENVS.backend.dir;
}

const child = spawn(python, args, { cwd, env, stdio: "inherit" });
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
child.on("exit", (code, signal) => process.exit(signal ? 1 : code ?? 0));
