import {app,BrowserWindow,ipcMain,session,dialog} from "electron";
import {spawn} from "node:child_process";
import {join,resolve} from "node:path";
import {homedir} from "node:os";
import {pathToFileURL} from "node:url";
import {writeFile} from "node:fs/promises";
import {SCHEMA,type Reply,type Snapshot,type ModelReply,type WorkerStatus} from "./protocol";
import {modelArgs} from "./model-actions";
const smoke=process.argv.includes("--studio-smoke");
const page=join(__dirname,"index.html");
const allowedURL=pathToFileURL(page).href;
// Trusted operator-selected executable path only; no renderer arguments or shell.
const python=process.env.RPDISTILL_PYTHON || (process.platform==="win32"?"python":"python3");
const db=resolve(process.env.RPDISTILL_DB || join(homedir(),".rpdistill","tasks.sqlite3"));
let pending:Promise<Reply>|undefined;
function query():Promise<Reply>{
  if(pending)return pending;
  pending=new Promise<Reply>(done=>{
    const child=spawn(python,["-m","rpdistill","--db",db,"studio-snapshot"],
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
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作正在运行"};
 assetWorker.running=true;assetWorker.message="正在获取固定版本分词器资源";
 const child=spawn(python,["-m","rpdistill","--db",db,"student-assets","--root",assets,"--max-bytes","4194304"],{
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
function startTraining():ModelReply{
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作正在运行"};
 trainingWorker.running=true;trainingWorker.message="正在执行队列首个已授权训练任务";
 const child=spawn(python,["-m","rpdistill","--db",db,"training-run"],{shell:false,windowsHide:true,
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
 if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作正在运行"};
 corpusWorker.running=true;corpusWorker.id=id;corpusWorker.message="正在执行单次语料流水线";
 const child=spawn(python,["-m","rpdistill","--db",db,"pipeline-run",id],{
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
 const child=spawn(python,["-m","rpdistill","--db",db,"download-run"],{
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
  if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作运行"};
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
 if(!win||worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running||modelPending)return {ok:false,error:"本地已有执行器或短操作运行"};
 evaluationWorker.running=true;evaluationWorker.message="等待选择人工审核 JSONL";
 let input:string;
 try{
  const selected=await dialog.showOpenDialog(win,{properties:["openFile"],filters:[{name:"人工参考译文 JSONL",extensions:["jsonl"]}]});
  if(selected.canceled||selected.filePaths.length!==1){evaluationWorker.running=false;evaluationWorker.message="已取消文件选择";return {ok:false,error:"已取消文件选择"}}
  input=selected.filePaths[0];
 }catch{evaluationWorker.running=false;return {ok:false,error:"文件选择失败"}}
 evaluationWorker.message="正在进行本地 CPU 学生模型评测";
 const child=spawn(python,["-m","rpdistill","--db",db,...args,"--input",input,"--root",evaluationRoot],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
 const chunks:Buffer[]=[];let size=0,failed=false;
 child.stdout.on("data",(chunk:Buffer)=>{size+=chunk.length;if(size<=1024*1024)chunks.push(chunk);else failed=true});
 child.stderr.resume();child.on("error",()=>{failed=true});
 child.on("close",code=>{evaluationWorker.running=false;
  if(code!==0||failed){evaluationWorker.message="评测失败，请核对评测集、检查点和依赖";return}
  try{const result=JSON.parse(Buffer.concat(chunks).toString("utf8"));evaluationWorker.message=result.state==="complete"?"评测报告已生成，非发布批准":"评测结果异常"}catch{evaluationWorker.message="评测响应异常"}
 });
 return {ok:true,data:{...evaluationWorker}};
}
function modelAction(request:unknown):Promise<ModelReply>{
 let args:string[];
 try{args=modelArgs(request)}catch{return Promise.resolve({ok:false,error:"请求无效：请核对参数、许可证和预算确认"})}
 if(args[0]==="worker-start"||args[0]==="worker-stop")return Promise.resolve(workerAction(args[0]));
 if(args[0]==="studio-evaluate")return startEvaluation(args);
 if(args[0]==="studio-evaluation-recover"&&evaluationWorker.running)return Promise.resolve({ok:false,error:"本地评测执行器仍运行"});
 if(args[0]==="student-assets")return Promise.resolve(startAssets());
 if(args[0]==="training-run")return Promise.resolve(startTraining());
 if(args[0]==="training-recover"&&trainingWorker.running)return Promise.resolve({ok:false,error:"本地训练执行器仍运行"});
 if(args[0]==="training-enqueue")args.push("--assets",assets,"--root",checkpointRoot);
 if(args[0]==="pipeline-run")return Promise.resolve(startCorpus(args[1]));
 if(args[0]==="pipeline-resume"&&corpusWorker.running)return Promise.resolve({ok:false,error:"本地语料执行器仍在运行"});
 if(args[0]==="download-recover"&&worker.running)return Promise.resolve({ok:false,error:"本地执行器仍在运行，不能恢复"});
 if(modelPending)return Promise.resolve({ok:false,error:"已有模型操作正在执行"});
 modelPending=true;
 return new Promise<ModelReply>(done=>{
  const child=spawn(python,["-m","rpdistill","--db",db,...args],{shell:false,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,PYTHONIOENCODING:"utf-8"}});
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
    if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running){event.preventDefault();dialog.showMessageBoxSync(win!,{type:"info",title:"执行器仍在运行",message:"请等待语料、学生资源或评测任务完成，或先暂停/取消模型下载及训练任务，再关闭窗口。"});}
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
    return reply.ok?{ok:true,data:{...reply.data,local_worker:{...worker},local_corpus_worker:{...corpusWorker},local_training_worker:{...trainingWorker},local_asset_worker:{...assetWorker},local_evaluation_worker:{...evaluationWorker}}}:reply;
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
app.on("before-quit",event=>{if(worker.running||corpusWorker.running||trainingWorker.running||assetWorker.running||evaluationWorker.running){event.preventDefault();if(win)dialog.showMessageBoxSync(win,{type:"info",message:"执行器仍在运行，请先结束当前任务。"});}});
app.on("window-all-closed",()=>{if(process.platform!=="darwin")app.quit()});
