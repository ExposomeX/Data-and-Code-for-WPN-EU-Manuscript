import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const vitePath = path.join(projectRoot, 'node_modules', 'vite', 'bin', 'vite.js');

const timeoutMs = 60000;
const buildArgs = process.argv.slice(2);
// Both projects use plain ESM JavaScript configs, so no config transpiler is needed.
if (!buildArgs.some((arg) => arg === '--configLoader' || arg.startsWith('--configLoader='))) {
  buildArgs.push('--configLoader', 'native');
}
let activeChild = null;
let interrupted = null;

function interrupt(signal) {
  interrupted = signal;
  // This handle belongs only to the build started by this wrapper.
  if (activeChild && activeChild.exitCode === null) activeChild.kill(signal);
}
const onSigint = () => interrupt('SIGINT');
const onSigterm = () => interrupt('SIGTERM');
process.on('SIGINT', onSigint);
process.on('SIGTERM', onSigterm);

function runBuild(nodePath, attempt) {
  return new Promise((resolve) => {
    const startedAt = Date.now();
    // Invoke Vite directly: never npm or this wrapper. Ignore unused stdin.
    const child = spawn(nodePath, [vitePath, 'build', ...buildArgs], {
      cwd: projectRoot, stdio: ['ignore', 'inherit', 'inherit'], windowsHide: true,
    });
    activeChild = child;
    let settled = false;
    let timedOut = false;
    let forceTimer;
    const heartbeat = setInterval(() => {
      console.log(`构建仍在进行：第 ${attempt} 次，已等待 ${Math.round((Date.now() - startedAt) / 1000)} 秒（PID ${child.pid}）。`);
    }, 15000);
    const timeout = setTimeout(() => {
      timedOut = true;
      console.error(`构建等待超过 ${timeoutMs / 1000} 秒，正在结束本工具启动的构建进程 ${child.pid}。`);
      child.kill('SIGTERM');
      forceTimer = setTimeout(() => {
        if (!settled) child.kill('SIGKILL');
      }, 5000);
    }, timeoutMs);
    function finish(exitCode, signal, error = null) {
      if (settled) return;
      settled = true;
      clearInterval(heartbeat);
      clearTimeout(timeout);
      clearTimeout(forceTimer);
      if (activeChild === child) activeChild = null;
      resolve({ attempt, pid: child.pid ?? null, exitCode, signal, timedOut,
        durationMs: Date.now() - startedAt, error: error?.message ?? null });
    }
    // Wait for the actual process exit, not a descendant's inherited pipe EOF.
    child.once('exit', (code, signal) => finish(code, signal));
    child.once('error', (error) => finish(null, null, error));
  });
}

async function main() {
  if (!fs.existsSync(vitePath)) {
    throw new Error('没有找到已安装的 Vite 构建依赖。请由网站维护者准备依赖后重试；本工具不会下载安装运行时。');
  }
  const nodePath = process.execPath;
  const nodeVersion = process.version;
  console.log(`构建运行时：Node.js ${nodeVersion}`);
  console.log(`运行时路径：${nodePath}`);
  const startedAt = Date.now();
  const attempts = [];
  for (let attempt = 1; attempt <= 2 && !interrupted; attempt++) {
    console.log(`开始第 ${attempt} 次网站构建（最长等待 ${timeoutMs / 1000} 秒）。`);
    const result = await runBuild(nodePath, attempt);
    attempts.push(result);
    if (!result.timedOut || interrupted || attempt === 2) break;
    console.warn('上次构建已因超时结束；现在仅自动重试一次。');
  }
  const result = attempts.at(-1);
  const indexPath = path.join(projectRoot, 'dist', 'index.html');
  const freshOutput = fs.existsSync(indexPath) && fs.statSync(indexPath).mtimeMs >= startedAt - 2000;
  const success = result?.exitCode === 0 && !result.timedOut && !interrupted && freshOutput;
  const record = {
    startedAt: new Date(startedAt).toISOString(), completedAt: new Date().toISOString(),
    nodePath, nodeVersion, timeoutMs, success, freshOutput, interrupted, attempts,
  };
  fs.mkdirSync(path.join(projectRoot, '.runtime'), { recursive: true });
  fs.writeFileSync(path.join(projectRoot, '.runtime', 'build-last.json'), JSON.stringify(record, null, 2) + '\n');
  if (success) {
    console.log('网站构建完成，已验证 dist/index.html 为本次新生成的文件。');
    return 0;
  }
  if (interrupted) {
    console.error(`网站构建被中断（${interrupted}）。`);
    return interrupted === 'SIGINT' ? 130 : 143;
  }
  if (result?.timedOut) {
    console.error('网站构建连续超时，已停止重试。请查看上面的构建日志。');
    return 124;
  }
  if (result?.error) console.error(`无法启动网站构建：${result.error}`);
  else if (result?.exitCode === 0 && !freshOutput) console.error('构建进程结束，但没有生成新的 dist/index.html，不能视为成功。');
  else console.error(`网站构建失败（退出码 ${result?.exitCode ?? '无'}${result?.signal ? `，${result.signal}` : ''}）。`);
  return typeof result?.exitCode === 'number' && result.exitCode !== 0 ? result.exitCode : 1;
}

try {
  process.exitCode = await main();
} catch (error) {
  console.error(`网站构建失败：${error.message}`);
  process.exitCode = 1;
} finally {
  process.removeListener('SIGINT', onSigint);
  process.removeListener('SIGTERM', onSigterm);
}
