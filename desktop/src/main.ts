import {app,BrowserWindow,ipcMain,session,dialog} from "electron";
import {spawn} from "node:child_process";
import {join,resolve} from "node:path";
import {homedir} from "node:os";
import {pathToFileURL} from "node:url";
import {writeFile,rename} from "node:fs/promises";
import {readFileSync,lstatSync,existsSync,readdirSync,realpathSync} from "node:fs";
import {randomUUID,createHash} from "node:crypto";
import {SCHEMA,type Reply,type Snapshot,type ModelReply,type WorkerStatus} from "./protocol";
import {modelArgs} from "./model-actions";
const smoke=process.argv.includes("--studio-smoke");
const page=join(__dirname,"index.html");
const allowedURL=pathToFileURL(page).href;
// Trusted operator-selected executable path only; no renderer arguments or shell.
const basePython=app.isPackaged&&process.platform==="win32"?join(process.resourcesPath,"backend","python.exe"):process.platform==="win32"?"python":"python3";
const envRoot=resolve(process.env.RPDISTILL_ENV_ROOT||join(homedir(),".rpdistill","environments"));
const override=process.env.RPDISTILL_PYTHON;
const activeFile=join(envRoot,"active.json");
const wheelDir=join(process.resourcesPath,"backend","wheels");
type Managed={schema:"rpdistill-managed-environment-v1";id:string;profile:"cpu"|"cu128";backend:string;torch:string;cuda_available:boolean;cuda_version:string|null;runtime_verified:true;wheel_sha256:string};
function wheelPath(){
 const names=readdirSync(wheelDir).filter(n=>/^rpdistill-[0-9.]+-py3-none-any\.whl$/.test(n));
 if(names.length!==1)throw Error("wheel");
 return join(wheelDir,names[0]);
}
function readManaged(id:unknown):Managed{
 if(typeof id!=="string"||!/^[a-f0-9]{32}$/.test(id))throw Error("id");
 const root=join(envRoot,id),exe=join(root,"Scripts","python.exe");
 for(const p of [envRoot,root,join(root,"Scripts"),exe,join(root,"verified.json")]){
  if(lstatSync(p).isSymbolicLink())throw Error("symlink");
 }
 if(!lstatSync(exe).isFile()||!lstatSync(join(root,"verified.json")).isFile()||lstatSync(join(root,"verified.json")).size>16384)throw Error("python");
 const m=JSON.parse(readFileSync(join(root,"verified.json"),"utf8")) as Managed;
 if(m.schema!=="rpdistill-managed-environment-v1")throw Error("schema");
 if(m.id!==id||m.runtime_verified!==true||!["cpu","cu128"].includes(m.profile)||m.backend!==app.getVersion()||
    m.wheel_sha256!==createHash("sha256").update(readFileSync(wheelPath())).digest("hex")||
    (m.profile==="cu128"&&(m.cuda_available!==true||m.cuda_version!=="12.8")))throw Error("receipt");
 return m;
}
let managed:Managed|null=null;
let envMessage="尚未部署独立训练环境";
if(!override&&!smoke&&app.isPackaged&&existsSync(activeFile)){
 try{const pin=JSON.parse(readFileSync(activeFile,"utf8"));if(pin.id!==null){managed=readManaged(pin.id);envMessage="已启用登记的训练环境（历史验证）"}else envMessage="已选择基础后端"}catch{envMessage="已登记环境无效或版本变化，已回退基础后端"}
}
let python=override||(managed?join(envRoot,managed.id,"Scripts","python.exe"):basePython);
const environmentWorker:WorkerStatus={running:false,stop_requested:false,message:envMessage};

const db=resolve(process.env.RPDISTILL_DB || join(homedir(),".rpdistill","tasks.sqlite3"));
let pending:Promise<Reply>|undefined;
function queryWith(executable:string):Promise<Reply>{
  return new Promise<Reply>(done=>{
    const child=spawn(executable,["-I","-m","rpdistill","--db",db,"studio-snapshot"],
      {shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],
       env:{...process.env,PYTHONIOENCODING:"utf-8"}});
    const chunks:Buffer[]=[];let size=0,settled=false;
    const finish=(r:Reply)=>{if(!settled){settled=true;clearTimeout(timer);done(r)}};
    const fail=(error:string)=>{child.kill();finish({ok:false,error})};
    const timer=setTimeout(()=>fail("后端查询超时"),15000);
    child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size>1024*1024){fail("后端响应超出限制");return}chunks.push(chunk)});
    child.stderr.resume();
    child.on("error",()=>finish({ok:false,error:"无法启动 Python 后端，请检查本地环境"}));
    child.on("close",code=>{
      if(settled)return;
      if(code!==0){finish({ok:false,error:"后端状态查询失败，请检查数据库与 Python 环境"});return}
      try{
        const value=JSON.parse(Buffer.concat(chunks).toString("utf8")) as Snapshot;
        if(value.schema!==SCHEMA||value.read_only!==true||!value.counts||!value.rows||!value.devices)
          throw Error("protocol");
        finish({ok:true,data:value});
      }catch{finish({ok:false,error:"后端协议不兼容"})}
    });
  });
}
let degraded=false;
function query():Promise<Reply>{
 if(pending)return pending;
 const executable=python;
 pending=queryWith(executable).then(async result=>{
  if(python!==executable)return result;
  degraded=!result.ok&&!!managed;
  if(degraded)return queryWith(basePython);
  return result;
 }).finally(()=>{pending=undefined});
 return pending;
}
// Only explicitly started, approved persistent jobs run. A worker never kills an active
// download on pause/stop: cooperative checkpoints and DB state remain authoritative.
const worker:WorkerStatus={running:false,stop_requested:false,message:"下载执行器未启动"};
const trainingWorker:WorkerStatus={running:false,stop_requested:false,message:"训练执行器未启动"};
const assets=resolve(process.env.RPDISTILL_STUDENT_ASSETS||join(homedir(),".rpdistill","student-assets"));
const checkpointRoot=resolve(process.env.RPDISTILL_CHECKPOINT_ROOT||join(homedir(),".rpdistill","checkpoints"));
const evaluationWorker:WorkerStatus={running:false,stop_requested:false,message:"评测执行器未启动"};
const evaluationRoot=resolve(process.env.RPDISTILL_EVALUATION_ROOT||join(homedir(),".rpdistill","evaluations"));
const assetWorker:WorkerStatus={running:false,stop_requested:false,message:"学生资源下载未启动"};
function startAssets():ModelReply{
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作正在运行"};
 assetWorker.running=true;assetWorker.message="正在获取固定版本分词器资源";
 const child=spawn(python,["-I","-m","rpdistill","--db",db,"student-assets","--root",assets,"--max-bytes","4194304"],{
  shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
 let size=0,failed=false;const chunks:Buffer[]=[];
 child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else failed=true});
 child.stderr.resume();child.on("error",()=>{failed=true});
 child.on("close",code=>{
  assetWorker.running=false;
  if(code!==0||failed){assetWorker.message="资源下载或校验失败，可重新确认预算后重试";return}
  try{const result=JSON.parse(Buffer.concat(chunks).toString("utf8"));
   assetWorker.message=result.weights_downloaded===false&&result.files===5?"固定资源已下载并校验":"资源响应异常，请重新核对校验状态";
  }catch{assetWorker.message="资源响应无效，请核对校验状态"}
 });
 return {ok:true,data:{...assetWorker}};
}
function startTraining(id?:string):ModelReply{
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作正在运行"};
 trainingWorker.running=true;trainingWorker.message=id?"正在执行指定已审核关联训练任务":"正在执行队列首个已授权训练任务";
 const child=spawn(python,["-I","-m","rpdistill","--db",db,"training-run",...(id?["--job-id",id]:[])],{shell:false,windowsHide:true,
  stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8",CUBLAS_WORKSPACE_CONFIG:":4096:8"}});
 let size=0,failed=false;const chunks:Buffer[]=[];
 child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else failed=true});
 child.stderr.resume();child.on("error",()=>{failed=true});
 child.on("close",code=>{
  trainingWorker.running=false;
  if(code!==0||failed){trainingWorker.message="训练执行器异常退出，请核对持久状态";return}
  try{const result=JSON.parse(Buffer.concat(chunks).toString("utf8"));
   trainingWorker.message=result===null?"没有待训练任务":"训练任务结束："+String(result.state);
  }catch{trainingWorker.message="训练执行器响应无效，请核对持久状态"}
 });
 return {ok:true,data:{...trainingWorker}};
}
const corpusWorker:{running:boolean;id:string|null;message:string}={running:false,id:null,message:"语料执行器未启动"};
function startCorpus(id:string):ModelReply{
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作正在运行"};
 corpusWorker.running=true;corpusWorker.id=id;corpusWorker.message="正在执行单次语料流水线";
 const child=spawn(python,["-I","-m","rpdistill","--db",db,"pipeline-run",id],{
  shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
 const chunks:Buffer[]=[];let size=0,failed=false;
 child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else failed=true});
 child.stderr.resume();
 child.on("error",()=>{failed=true});
 child.on("close",code=>{
  corpusWorker.running=false;
  if(code!==0||failed){corpusWorker.message="语料执行器退出异常，请核对持久任务状态";return}
  try{
   const result=JSON.parse(Buffer.concat(chunks).toString("utf8")) as {state?:string};
   corpusWorker.message=result.state==="candidate_complete"?"候选数据集已生成，仍需人工权利与质量复核":
    result.state==="insufficient_candidates"?"候选数量不足，未通过数据门槛":"语料任务结束，请核对持久状态";
  }catch{corpusWorker.message="语料响应无效，请核对持久状态"}
 });
 return {ok:true,data:{...corpusWorker}};
}
function finishWorker(message:string){
 worker.running=false;worker.stop_requested=false;worker.message=message;
}
function nextDownload(){
 if(worker.stop_requested){finishWorker("执行器已停止接收新任务");return}
 worker.message="正在执行队列中的任务";
 const child=spawn(python,["-I","-m","rpdistill","--db",db,"download-run"],{
  shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
 const chunks:Buffer[]=[];let size=0,failed=false;
 child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else failed=true});
 child.stderr.resume();
 child.on("error",()=>{failed=true});
 child.on("close",code=>{
  if(code!==0||failed){finishWorker("执行器异常退出或其他执行器占用队列；请核对任务状态");return}
  try{
   const result=JSON.parse(Buffer.concat(chunks).toString("utf8")) as {state?:string}|null;
   if(result===null){finishWorker("没有待下载任务");return}
   if(result.state!=="succeeded"){finishWorker("本轮在非成功任务后停止，请检查队列");return}
   if(worker.stop_requested){finishWorker("当前任务已结束，执行器已停止");return}
   // Yield to IPC between jobs; the SQLite queue enforces cross-process ownership.
   setImmediate(nextDownload);
  }catch{finishWorker("执行器响应无效，请核对任务状态")}
 });
}
function workerAction(kind:string):ModelReply{
 if(kind==="worker-start"){
  if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作运行"};
  worker.running=true;worker.stop_requested=false;worker.message="正在启动执行器";
  setImmediate(nextDownload);
  return {ok:true,data:{...worker}};
 }
 if(!worker.running)return {ok:false,error:"本地下载执行器未运行"};
 worker.stop_requested=true;worker.message="当前任务结束后停止；可使用任务暂停或取消";
 return {ok:true,data:{...worker}};
}
let modelPending=false;
async function startEvaluation(args:string[]):Promise<ModelReply>{
 if(!win||worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作运行"};
 evaluationWorker.running=true;evaluationWorker.message="等待选择人工审核 JSONL";
 let input:string;
 try{
  const selected=await dialog.showOpenDialog(win,{properties:["openFile"],filters:[{name:"人工参考译文 JSONL",extensions:["jsonl"]}]});
  if(selected.canceled||selected.filePaths.length!==1){evaluationWorker.running=false;evaluationWorker.message="已取消文件选择";return {ok:false,error:"已取消文件选择"}}
  input=selected.filePaths[0];
 }catch{evaluationWorker.running=false;return {ok:false,error:"文件选择失败"}}
 evaluationWorker.message="正在进行本地 CPU 学生模型评测";
 const child=spawn(python,["-I","-m","rpdistill","--db",db,...args,"--input",input,"--root",evaluationRoot],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
 const chunks:Buffer[]=[];let size=0,failed=false;
 child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else failed=true});
 child.stderr.resume();child.on("error",()=>{failed=true});
 child.on("close",code=>{evaluationWorker.running=false;
  if(code!==0||failed){evaluationWorker.message="评测失败，请核对评测集、检查点和依赖";return}
  try{const result=JSON.parse(Buffer.concat(chunks).toString("utf8"));evaluationWorker.message=result.state==="complete"?"评测报告已生成，非发布批准":"评测结果异常"}catch{evaluationWorker.message="评测响应异常"}
 });
 return {ok:true,data:{...evaluationWorker}};
}
function startArtifact(args:string[]):ModelReply{
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作运行"};
 evaluationWorker.running=true;evaluationWorker.message="正在构建或评测本地候选模型";
 const root=resolve(process.env.RPDISTILL_ARTIFACT_ROOT||join(homedir(),".rpdistill","artifacts"));
 const child=spawn(python,["-I","-m","rpdistill","--db",db,...args,"--evaluation-root",evaluationRoot,"--root",root],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
 const chunks:Buffer[]=[];let size=0,failed=false;
 child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else failed=true});
 child.stderr.resume();child.on("error",()=>{failed=true});
 child.on("close",code=>{evaluationWorker.running=false;
  if(code!==0||failed){evaluationWorker.message="候选构建或回归失败，请核对预算及评测";return}
  try{const result=JSON.parse(Buffer.concat(chunks).toString("utf8"));evaluationWorker.message=result.state==="complete"?"候选任务完成，非发布批准":"候选结果异常"}catch{evaluationWorker.message="候选响应异常"}
 });
 return {ok:true,data:{...evaluationWorker}};
}
async function startReview(args:string[]):Promise<ModelReply>{
 if(!win||worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作运行"};
 const mode=args[3];
 evaluationWorker.running=true;evaluationWorker.message="正在准备本地复核";
 if(mode==="rust"||mode==="integration"){
  const exe=process.env.RPDISTILL_RUST_BRIDGE;
  if(!exe){evaluationWorker.running=false;return {ok:false,error:"请先在可信启动环境配置 RPDISTILL_RUST_BRIDGE"}}
  args.push("--executable",resolve(exe));
 }else if(mode==="blind"||mode==="collect"){
  try{
   const selected=await dialog.showOpenDialog(win,{properties:["openFile"],filters:[{name:mode==="blind"?"基线译文 JSONL":"独立评审 JSON",extensions:[mode==="blind"?"jsonl":"json"]}]});
   if(selected.canceled||selected.filePaths.length!==1){evaluationWorker.running=false;return {ok:false,error:"已取消文件选择"}}
   args.push("--input",selected.filePaths[0]);
  }catch{evaluationWorker.running=false;return {ok:false,error:"文件选择失败"}}
 }
 const root=resolve(process.env.RPDISTILL_REVIEW_ROOT||join(homedir(),".rpdistill","reviews"));
 const artifactRoot=resolve(process.env.RPDISTILL_ARTIFACT_ROOT||join(homedir(),".rpdistill","artifacts"));
 evaluationWorker.message="正在进行本地诊断或人工复核";
 const child=spawn(python,["-I","-m","rpdistill","--db",db,...args,"--evaluation-root",evaluationRoot,"--artifact-root",artifactRoot,"--root",root],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
 const chunks:Buffer[]=[];let size=0,failed=false;
 child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else failed=true});
 child.stderr.resume();child.on("error",()=>{failed=true});
 child.on("close",code=>{evaluationWorker.running=false;
  if(code!==0||failed){evaluationWorker.message="诊断或复核失败，请检查输入和可信桥接程序";return}
  try{const result=JSON.parse(Buffer.concat(chunks).toString("utf8"));evaluationWorker.message=result.state==="complete"?"本地复核记录已生成，非发布批准":"复核响应异常"}catch{evaluationWorker.message="复核响应异常"}
 });
 return {ok:true,data:{...evaluationWorker}};
}
function environmentInventory(){
 if(!app.isPackaged||override||smoke)return [];
 try{
  if(lstatSync(envRoot).isSymbolicLink())return [];
  return readdirSync(envRoot,{withFileTypes:true}).filter(d=>d.isDirectory()&&!d.isSymbolicLink()&&/^[a-f0-9]{32}$/.test(d.name)).sort((a,b)=>a.name.localeCompare(b.name)).slice(0,50).map(d=>{
   try{const m=readManaged(d.name);return {id:d.name,profile:m.profile,torch:m.torch,state:"verified" as const}}
   catch{return {id:d.name,profile:null,torch:null,state:"unavailable" as const}}
  });
 }catch{return []}
}
async function activateEnvironment(next:Managed|null){
 if(!existsSync(envRoot))throw Error("environment root missing");
 if(lstatSync(envRoot).isSymbolicLink())throw Error("environment root linked");
 const tmp=join(envRoot,"active-"+randomUUID()+".json");
 await writeFile(tmp,JSON.stringify({id:next?.id??null}),{flag:"wx"});
 await rename(tmp,activeFile);
 managed=next;python=next?join(envRoot,next.id,"Scripts","python.exe"):basePython;degraded=false;
}
async function selectEnvironment(id:string):Promise<ModelReply>{
 if(!win||!app.isPackaged||override||smoke||process.platform!=="win32")return {ok:false,error:"安装版且无外部覆盖时才可切换"};
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器"};
 environmentWorker.running=true;environmentWorker.message="检查持久任务及目标环境";
 try{
  // The bundled backend can inspect the DB even if the selected Python is broken.
  const state=await queryWith(basePython);
  if(!state.ok||["download_active","pipeline_active","training_active","evaluation_active","artifact_active","review_active","plan_active"].some(k=>state.data.counts[k]>0))throw Error("active");
  if(id==="base"){
   if(managed||existsSync(activeFile))await activateEnvironment(null);
   environmentWorker.message="已切换基础后端，训练环境仍保留";
   environmentWorker.running=false;
   return {ok:true,data:{...environmentWorker}};
  }
  const expected=readManaged(id);
  environmentWorker.message="离线重新验证历史环境";
  const child=spawn(basePython,["-I","-m","rpdistill.studio_environment","--wheel",wheelPath(),"--root",envRoot,"--recheck-id",id,"--approved"],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
  let size=0,failed=false;const chunks:Buffer[]=[];
  child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=65536)chunks.push(chunk);else failed=true});
  child.stderr.resume();child.on("error",()=>{failed=true});
  child.on("close",async code=>{
   try{
    if(code!==0||failed)throw Error("recheck");
    const lines=Buffer.concat(chunks).toString("utf8").trim().split("\n").map(x=>JSON.parse(x));
    const result=lines[lines.length-1];
    if(result.stage!=="complete"||result.id!==id)throw Error("recheck identity");
    const next=readManaged(id);
    if(JSON.stringify(next)!==JSON.stringify(expected))throw Error("receipt changed");
    await activateEnvironment(next);
    environmentWorker.message="历史环境重新验证通过并启用";
   }catch{environmentWorker.message="重新验证失败，未切换当前环境；可新建环境修复"}
   finally{environmentWorker.running=false}
  });
  return {ok:true,data:{...environmentWorker}};
 }catch{environmentWorker.running=false;environmentWorker.message="无法切换：请核对持久任务或环境记录";return {ok:false,error:environmentWorker.message}}
}
async function startEnvironment(profile:string):Promise<ModelReply>{
 if(!win||!app.isPackaged||override||smoke||process.platform!=="win32")return {ok:false,error:"仅正式安装候选可部署；请取消外部环境覆盖后重启"};
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器"};
 environmentWorker.running=true;environmentWorker.message="检查当前持久任务";
 try{
  const state=await query();
  if(!state.ok||["download_active","pipeline_active","training_active","evaluation_active","artifact_active","review_active","plan_active"].some(k=>state.data.counts[k]>0))throw Error("active");
  const wheel=wheelPath();
  const choice=await dialog.showOpenDialog(win,{title:"选择可信的 64 位 Python 3.11 或 3.12 python.exe",properties:["openFile"],filters:[{name:"Python executable",extensions:["exe"]}]});
  if(choice.canceled||choice.filePaths.length!==1){environmentWorker.running=false;environmentWorker.message="已取消";return {ok:false,error:"已取消选择"}}
  const selected=realpathSync(choice.filePaths[0]);
  if(!/[/\\]python\.exe$/i.test(selected)||!lstatSync(selected).isFile())throw Error("python");
  const confirm=await dialog.showMessageBox(win,{type:"warning",buttons:["取消","确认部署"],defaultId:0,cancelId:0,
    title:"确认可信 Python 与联网安装",message:"仅运行你信任的 Python；创建新虚拟环境并联网安装依赖。",detail:selected+"\n配置："+profile+"；安装可能消耗大量流量和磁盘，不是硬预算。"});
  if(confirm.response!==1){environmentWorker.running=false;environmentWorker.message="已取消";return {ok:false,error:"已取消部署"}}
  environmentWorker.message="正在检查 Python";
  const child=spawn(basePython,["-I","-m","rpdistill.studio_environment","--python",selected,"--wheel",wheel,"--root",envRoot,"--profile",profile,"--approved"],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
  let buffer="",total=0,failed=false,id:string|undefined;
  const stages:Record<string,string>={"python-probe":"验证 Python 版本和架构","venv":"创建独立虚拟环境","torch":"安装固定 PyTorch（联网）","dependencies":"安装模型 SDK 和评测依赖（联网）","verify":"验证依赖及真实张量计算","failed":"部署失败，保留原环境","complete":"正在登记新环境"};
  child.stdout.on("data",(chunk:Buffer)=>{
   total+=chunk.length;if(total>65536){failed=true;return}
   buffer+=chunk.toString("utf8");let pos:number;
   while((pos=buffer.indexOf("\n"))>=0){const line=buffer.slice(0,pos);buffer=buffer.slice(pos+1);try{const v=JSON.parse(line);environmentWorker.message=stages[v.stage]??"部署进行中";if(v.stage==="complete"&&/^[a-f0-9]{32}$/.test(v.id))id=v.id}catch{failed=true}}
  });
  child.stderr.resume();child.on("error",()=>{failed=true});
  child.on("close",async code=>{
   try{
    if(code!==0||failed||!id)throw Error("deployment");
    const next=readManaged(id);
    await activateEnvironment(next);
    environmentWorker.message="新训练环境已启用，实际 GPU 训练仍需验收";
   }catch{environmentWorker.message="部署或登记失败；原环境未切换，可重新授权创建新环境"}
   finally{environmentWorker.running=false}
  });
  return {ok:true,data:{...environmentWorker}};
 }catch{environmentWorker.running=false;environmentWorker.message="预检或选择失败；原环境未改变";return {ok:false,error:environmentWorker.message}}
}
const planWorker:WorkerStatus&{id:string|null;in_cycle:boolean}={running:false,stop_requested:false,message:"计划调度未启动",id:null,in_cycle:false};
let planTimer:ReturnType<typeof setTimeout>|undefined;
function finishPlan(message:string){
 if(planTimer)clearTimeout(planTimer);planTimer=undefined;
 planWorker.running=false;planWorker.stop_requested=false;planWorker.in_cycle=false;planWorker.id=null;planWorker.message=message;
}
function nextPlan(){
 planTimer=undefined;
 if(planWorker.in_cycle)return;
 if(!planWorker.running||!planWorker.id||planWorker.stop_requested){finishPlan("已停止后续轮次");return}
 const id=planWorker.id;
 planWorker.in_cycle=true;planWorker.message="检查计划到期或执行已授权轮次";
 const child=spawn(python,["-I","-m","rpdistill","--db",db,"plan-tick",id,"--approved"],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
 const chunks:Buffer[]=[];let size=0,failed=false;
 child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else failed=true});
 child.stderr.resume();child.on("error",()=>{failed=true});
 child.on("close",code=>{
  planWorker.in_cycle=false;
  if(code!==0||failed){finishPlan("计划执行异常，核对持久状态；不自动重试");return}
  try{
   const r=JSON.parse(Buffer.concat(chunks).toString("utf8"));
   if(r.id!==id)throw Error("plan identity");
   if(planWorker.stop_requested){finishPlan("当前轮次结束，已停止后续调度");return}
   if(r.state==="complete"){finishPlan("全部授权轮次已完成；候选仍需审核");return}
   if(r.state!=="ready"&&r.state!=="waiting"){finishPlan("计划已停止：候选不足或执行失败");return}
   const due=Date.parse(r.next_due);if(!Number.isFinite(due))throw Error("due");
   planWorker.message="等待下一授权轮次："+r.next_due;
   planTimer=setTimeout(nextPlan,Math.max(1000,Math.min(60000,due-Date.now())));
  }catch{finishPlan("计划响应异常；不自动重试")}
 });
}
function startPlan(id:string):ModelReply{
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running||modelPending)return {ok:false,error:"本地已有执行器"};
 planWorker.id=id;planWorker.running=true;planWorker.stop_requested=false;planWorker.message="计划调度已启动";
 planTimer=setTimeout(nextPlan,0);
 return {ok:true,data:{...planWorker}};
}
function stopPlan():ModelReply{
 if(!planWorker.running)return {ok:false,error:"本地计划调度未启动"};
 planWorker.stop_requested=true;
 if(!planWorker.in_cycle)finishPlan("已停止后续轮次，计划预算保留");
 else planWorker.message="当前轮次结束后停止；不强制终止下载";
 return {ok:true,data:{...planWorker}};
}
async function exportReviewDataset(version:string):Promise<ModelReply>{
 if(!win||modelPending||worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running)return {ok:false,error:"本地已有执行器或短操作"};
 modelPending=true;
 try{
  const selected=await dialog.showSaveDialog(win,{title:"保存待人工审核的候选数据集（本地 JSONL）",defaultPath:"dataset-"+version.slice(0,12)+".jsonl",filters:[{name:"候选数据 JSONL",extensions:["jsonl"]}]});
  if(selected.canceled||!selected.filePath){modelPending=false;return {ok:false,error:"已取消导出"}}
  if(existsSync(selected.filePath)){modelPending=false;return {ok:false,error:"只允许新文件，请另选路径"}}
  return await new Promise<ModelReply>(done=>{
   const child=spawn(python,["-I","-m","rpdistill","--db",db,"dataset-export",version,"--output="+selected.filePath],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
   let size=0,failed=false;const chunks:Buffer[]=[];
   const timer=setTimeout(()=>{failed=true;child.kill()},45000);
   child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else{failed=true;child.kill()}});
   child.stderr.resume();child.on("error",()=>{failed=true});
   child.on("close",code=>{
    clearTimeout(timer);modelPending=false;
    if(code!==0||failed){done({ok:false,error:"数据导出失败，请核对候选完整性与输出文件"});return}
    try{const r=JSON.parse(Buffer.concat(chunks).toString("utf8"));if(r.version!==version||r.training_ready!==false)throw Error("identity");done({ok:true,data:{version}})}catch{done({ok:false,error:"导出响应异常，请核对文件"})}
   });
  });
 }catch{modelPending=false;return {ok:false,error:"无法导出审核文件"}}
}
function modelAction(request:unknown):Promise<ModelReply>{
 let args:string[];
 try{args=modelArgs(request)}catch{return Promise.resolve({ok:false,error:"请求无效：请核对参数、许可证和预算确认"})}
 if(args[0]==="plan-stop")return Promise.resolve(stopPlan());
 if(planWorker.running)return Promise.resolve({ok:false,error:"请先停止周期计划，再操作其他任务"});
 if(args[0]==="plan-start"){if(degraded)return Promise.resolve({ok:false,error:"训练环境不可用"});return Promise.resolve(startPlan(args[1]));}
 if(args[0]==="environment-deploy")return startEnvironment(args[1]);
 if(args[0]==="environment-select")return selectEnvironment(args[1]);
 if(degraded)return Promise.resolve({ok:false,error:"当前训练环境不可用，请在设置中切换基础后端或重新部署"});
 if(environmentWorker.running)return Promise.resolve({ok:false,error:"训练环境正在部署，暂不可操作任务"});
 if(args[0]==="worker-start"||args[0]==="worker-stop")return Promise.resolve(workerAction(args[0]));
 if(args[0]==="studio-review")return startReview(args);
 if(args[0]==="studio-review-recover"&&evaluationWorker.running)return Promise.resolve({ok:false,error:"本地复核执行器仍运行"});
 if(args[0]==="studio-artifact")return Promise.resolve(startArtifact(args));
 if(args[0]==="studio-artifact-recover"&&evaluationWorker.running)return Promise.resolve({ok:false,error:"本地候选执行器仍运行"});
 if(args[0]==="studio-evaluate")return startEvaluation(args);
 if(args[0]==="studio-evaluation-recover"&&evaluationWorker.running)return Promise.resolve({ok:false,error:"本地评测执行器仍运行"});
 if(args[0]==="student-assets")return Promise.resolve(startAssets());
 if(args[0]==="dataset-review-export")return exportReviewDataset(args[1]);
 if(args[0]==="training-run")return Promise.resolve(startTraining(args[1]));
 if(args[0]==="training-recover"&&trainingWorker.running)return Promise.resolve({ok:false,error:"本地训练执行器仍运行"});
 if(args[0]==="training-enqueue")args.push("--assets",assets,"--root",checkpointRoot);
 if(args[0]==="pipeline-run")return Promise.resolve(startCorpus(args[1]));
 if(args[0]==="pipeline-resume"&&corpusWorker.running)return Promise.resolve({ok:false,error:"本地语料执行器仍在运行"});
 if(args[0]==="download-recover"&&worker.running)return Promise.resolve({ok:false,error:"本地执行器仍在运行，不能恢复"});
 if(modelPending)return Promise.resolve({ok:false,error:"已有模型操作正在执行"});
 modelPending=true;
 return new Promise<ModelReply>(done=>{
  const child=spawn(python,["-I","-m","rpdistill","--db",db,...args],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
  let size=0,settled=false;const chunks:Buffer[]=[];
  const finish=(r:ModelReply)=>{if(!settled){settled=true;clearTimeout(timer);done(r)}};
  const fail=(error:string)=>{child.kill();finish({ok:false,error})};
  const timer=setTimeout(()=>fail("模型操作超时，请刷新队列核对实际状态"),45000);
  child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size>1024*1024){fail("模型响应超出限制");return}chunks.push(chunk)});
  child.stderr.resume();
  child.on("error",()=>{finish({ok:false,error:"无法启动 Python 后端"})});
  child.on("close",code=>{
   modelPending=false;
   if(settled)return;
   if(code!==0){finish({ok:false,error:"操作失败，请检查网络、SDK、模型信息或任务状态"});return}
   try{finish({ok:true,data:JSON.parse(Buffer.concat(chunks).toString("utf8"))})}catch{finish({ok:false,error:"后端模型响应无效"})}
  });
 });
}
let win:BrowserWindow|null=null;
function create(){
  win=new BrowserWindow({width:1672,height:941,useContentSize:true,minWidth:1000,minHeight:650,
    show:!smoke,backgroundColor:"#10141d",title:"RPDistill Studio",
    titleBarStyle:"hidden",titleBarOverlay:{color:"#101827",symbolColor:"#e8eef9",height:42},
    webPreferences:{preload:join(__dirname,"preload.cjs"),contextIsolation:true,nodeIntegration:false,
      sandbox:true,webSecurity:true,offscreen:smoke,additionalArguments:smoke?["--studio-smoke"]:[]}});
  win.webContents.setWindowOpenHandler(()=>({action:"deny"}));
  win.webContents.on("will-navigate",(e,url)=>{if(url!==allowedURL)e.preventDefault()});
  win.webContents.on("will-attach-webview",e=>e.preventDefault());
  win.on("close",event=>{
    if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running){event.preventDefault();dialog.showMessageBoxSync(win!,{type:"info",title:"执行器仍在运行",message:"请先停止周期计划，等待当前轮次、环境部署、语料或评测结束，或暂停/取消下载及训练，再关闭窗口。"});}
  });
  win.on("closed",()=>{win=null});
  if(smoke)win.setContentSize(1672,941);
  void win.loadFile(page);
}
app.whenReady().then(()=>{
  session.defaultSession.setPermissionRequestHandler((_wc,_permission,cb)=>cb(false));
  session.defaultSession.setPermissionCheckHandler(()=>false);
  ipcMain.handle("studio:snapshot",async(event)=>{
    if(!win||event.sender!==win.webContents||event.senderFrame?.url!==allowedURL||
       event.senderFrame!==win.webContents.mainFrame)return {ok:false,error:"请求来源无效"} satisfies Reply;
    const reply=await query();
    return reply.ok?{ok:true,data:{...reply.data,local_worker:{...worker},local_corpus_worker:{...corpusWorker},local_training_worker:{...trainingWorker},local_asset_worker:{...assetWorker},local_evaluation_worker:{...evaluationWorker},local_environment_worker:{...environmentWorker},local_plan_worker:{...planWorker},environment:{deploy_available:app.isPackaged&&!override&&!smoke,source:override?"external":managed?"managed":"base",profile:managed?.profile??null,torch:managed?.torch??null,cuda_available:managed?.cuda_available??null,active_id:managed?.id??null,degraded,inventory:environmentInventory()}}}:reply;
  });
  ipcMain.handle("studio:model-action",(event,request:unknown)=>{
    if(!win||event.sender!==win.webContents||event.senderFrame?.url!==allowedURL||
       event.senderFrame!==win.webContents.mainFrame)return {ok:false,error:"请求来源无效"} satisfies ModelReply;
    return modelAction(request);
  });
  if(smoke){
    ipcMain.handle("studio:smoke-result",async(event,value:unknown)=>{
      if(win&&event.sender===win.webContents&&event.senderFrame?.url===allowedURL&&event.senderFrame===win.webContents.mainFrame){
        let ok=value===true;
        const output=process.env.RPDISTILL_SMOKE_SCREENSHOT;
        if(ok&&output){
          try{
            const image=await win.webContents.capturePage();
            if(image.isEmpty())throw Error("empty screenshot");
            await writeFile(output,image.toPNG());
            const size=image.getSize();
            console.log("studio_screenshot="+size.width+"x"+size.height);
          }catch{ok=false}
        }
        console.log("studio_smoke="+String(ok));app.exit(ok?0:1);
      }
    });
    setTimeout(()=>app.exit(1),120000).unref();
  }
  create();
  app.on("activate",()=>{if(!win)create()});
});
app.on("before-quit",event=>{if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||environmentWorker.running||planWorker.running){event.preventDefault();if(win)dialog.showMessageBoxSync(win,{type:"info",message:"执行器仍在运行，请先结束当前任务。"});}});
app.on("window-all-closed",()=>{if(process.platform!=="darwin")app.quit()});
