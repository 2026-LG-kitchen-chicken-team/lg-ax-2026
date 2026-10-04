// Reinstalls apps/web dependencies only when nothing is using them. `npm ci` deletes node_modules first, so running it
// while the Vite dev server (or a Playwright run that started one) holds esbuild open leaves a half-installed tree and
// breaks that server; on Windows the locked files cannot even be removed. This refuses instead of trying.
//   npm run ci:safe --prefix apps/web      (from the repository root)
import { spawnSync } from 'node:child_process';
import { connect } from 'node:net';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
// 5173: `npm run dev` and the Playwright webServer (vite --strictPort). Extra ports can be given as arguments.
const PORTS = [5173, ...process.argv.slice(2).map(Number).filter(Number.isInteger)];

export function listening(port, host = '127.0.0.1', timeoutMs = 500) {
  return new Promise(done => {
    const socket = connect({ port, host });
    const finish = value => { socket.destroy(); done(value); };
    socket.setTimeout(timeoutMs, () => finish(false));
    socket.once('connect', () => finish(true));
    socket.once('error', () => finish(false));
  });
}

async function main() {
  const busy = [];
  for (const port of PORTS) if (await listening(port)) busy.push(port);
  if (busy.length) {
    console.error(`[ci:safe] 포트 ${busy.join(', ')}에서 개발 서버가 실행 중입니다. npm ci는 node_modules를 지우므로 그 서버가 깨집니다.`);
    console.error('[ci:safe] 서버를 멈춘 뒤 다시 실행하거나, 별도 worktree에서 설치하세요: git worktree add <경로> <브랜치>');
    return 2;
  }
  const result = spawnSync('npm', ['ci', '--no-audit', '--no-fund'], { cwd: WEB, stdio: 'inherit', shell: process.platform === 'win32' });
  return result.status ?? 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main();
