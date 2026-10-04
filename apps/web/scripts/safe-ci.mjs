// Checks configured local dev ports before reinstalling dependencies. This is not a process or filesystem lock.
// `npm ci` deletes node_modules first, so running it
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

export function listening(port, host = '127.0.0.1', timeoutMs = 500, connectSocket = connect) {
  return new Promise((done, reject) => {
    const socket = connectSocket({ port, host });
    let settled = false;
    const finish = value => { if (settled) return; settled = true; socket.destroy(); done(value); };
    const fail = error => { if (settled) return; settled = true; socket.destroy(); reject(error); };
    socket.setTimeout(timeoutMs, () => fail(new Error('Port observation timed out')));
    socket.once('connect', () => finish(true));
    socket.once('error', error => error.code === 'ECONNREFUSED' ? finish(false) : fail(error));
  });
}

export async function main({ ports = PORTS, probe = listening, install = () => spawnSync('npm', ['ci', '--no-audit', '--no-fund'], { cwd: WEB, stdio: 'inherit', shell: process.platform === 'win32' }), log = console.error } = {}) {
  const busy = [];
  try {
    for (const port of ports) if (await probe(port)) busy.push(port);
  } catch {
    log('[ci:safe] 포트 상태를 확인하지 못했습니다. 설치를 중단합니다.');
    return 2;
  }
  if (busy.length) {
    log(`[ci:safe] 포트 ${busy.join(', ')}에서 개발 서버가 실행 중입니다. npm ci는 node_modules를 지우므로 그 서버가 깨집니다.`);
    log('[ci:safe] 해당 작업 폴더의 서버/검사를 멈춘 뒤 설치하세요. 이 검사는 다른 프로세스나 설치 경쟁의 안전을 보장하지 않습니다.');
    return 2;
  }
  const result = install();
  return result.status ?? 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main();
