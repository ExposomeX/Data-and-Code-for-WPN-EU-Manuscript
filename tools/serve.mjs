// Compatibility entry for npm run preview. The Python process serves both the
// website and model API; the desktop launchers start that same process directly.
import {spawn} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
if(!fs.existsSync(python))throw new Error('Run the first-time environment setup before starting WPN.');
const config=JSON.parse(fs.readFileSync(path.join(root,'项目配置.json'),'utf8').replace(/^\uFEFF/,''));
const child=spawn(python,['-X','utf8','-u',path.join(root,'api','server.py'),'--port',String(config.port||4174)],{cwd:root,stdio:'inherit',windowsHide:true});
child.on('error',error=>{console.error('Unable to start the local WPN model service:',error.message);process.exitCode=1});
child.on('exit',code=>{process.exitCode=code||0});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill(signal));
