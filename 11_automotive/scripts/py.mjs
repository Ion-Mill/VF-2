// backend/.venv 의 python 을 작업 폴더 backend 에서 실행한다 (Windows: .venv\Scripts\python.exe, macOS·Linux: .venv/bin/python)
// npm 스크립트는 Windows에서 cmd.exe 로 돌아 ".venv/Scripts/python" 경로를 못 읽으므로 이걸 거친다.
//   node scripts/py.mjs api          API 개발 서버 (:8000, --reload). 환경 파일 = MOM_ENV_FILE (기본 .env.supabase)
//   node scripts/py.mjs -m pip ...   그 밖의 인자는 python 에 그대로 넘김
// (Node 24는 스크립트 뒤 인자의 --env-file 까지 자기 옵션으로 읽으므로 uvicorn 의 --env-file 은 여기서 붙인다)
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const backend = join(dirname(fileURLToPath(import.meta.url)), "..", "backend");
const python = process.platform === "win32"
  ? join(backend, ".venv", "Scripts", "python.exe")
  : join(backend, ".venv", "bin", "python");

if (!existsSync(python)) {
  console.error(`가상환경이 없음: ${python}\n먼저 11_automotive 에서 npm run setup:api`);
  process.exit(1);
}

let args = process.argv.slice(2);
if (args[0] === "api") {
  const envFile = process.env.MOM_ENV_FILE || ".env.supabase";
  if (!existsSync(join(backend, envFile))) {
    console.error(`환경 파일이 없음: backend/${envFile}\n${envFile}.example 을 복사해 값을 채운다 (Docker DB면 MOM_ENV_FILE=.env)`);
    process.exit(1);
  }
  args = ["-m", "uvicorn", "app.main:app", "--env-file", envFile, "--reload", "--port", "8000", ...args.slice(1)];
}

const child = spawn(python, args, { cwd: backend, stdio: "inherit" });
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
child.on("exit", (code, signal) => process.exit(signal ? 1 : code ?? 0));
