import {app,BrowserWindow,ipcMain,session,dialog} from "electron";
import {spawn} from "node:child_process";
import {join,resolve} from "node:path";
import {homedir} from "node:os";
import {pathToFileURL} from "node:url";
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
  if(worker.running)return {ok:false,error:"本地下载执行器已运行"};
  worker.running=true;worker.stop_requested=false;worker.message="正在启动执行器";
  setImmediate(nextDownload);
  return {ok:true,data:{...worker}};
 }
 if(!worker.running)return {ok:false,error:"本地下载执行器未运行"};
 worker.stop_requested=true;worker.message="当前任务结束后停止；可使用任务暂停或取消";
 return {ok:true,data:{...worker}};
}
let modelPending=false;
function modelAction(request:unknown):Promise<ModelReply>{
 let args:string[];
 try{args=modelArgs(request)}catch{return Promise.resolve({ok:false,error:"请求无效：请核对参数、许可证和预算确认"})}
 if(args[0]==="worker-start"||args[0]==="worker-stop")return Promise.resolve(workerAction(args[0]));
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
  win=new BrowserWindow({width:1672,height:941,minWidth:1000,minHeight:650,
    show:!smoke,backgroundColor:"#10141d",title:"RPDistill Studio",
    webPreferences:{preload:join(__dirname,"preload.cjs"),contextIsolation:true,nodeIntegration:false,
      sandbox:true,webSecurity:true,additionalArguments:smoke?["--studio-smoke"]:[]}});
  win.webContents.setWindowOpenHandler(()=>({action:"deny"}));
  win.webContents.on("will-navigate",(e,url)=>{if(url!==allowedURL)e.preventDefault()});
  win.webContents.on("will-attach-webview",e=>e.preventDefault());
  win.on("close",event=>{
    if(worker.running){event.preventDefault();dialog.showMessageBoxSync(win!,{type:"info",title:"下载执行器仍在运行",message:"请先暂停或取消当前任务，或等待当前任务结束，再关闭窗口。"});}
  });
  win.on("closed",()=>{win=null});
  void win.loadFile(page);
}
app.whenReady().then(()=>{
  session.defaultSession.setPermissionRequestHandler((_wc,_permission,cb)=>cb(false));
  session.defaultSession.setPermissionCheckHandler(()=>false);
  ipcMain.handle("studio:snapshot",async(event)=>{
    if(!win||event.sender!==win.webContents||event.senderFrame?.url!==allowedURL||
       event.senderFrame!==win.webContents.mainFrame)return {ok:false,error:"请求来源无效"} satisfies Reply;
    const reply=await query();
    return reply.ok?{ok:true,data:{...reply.data,local_worker:{...worker}}}:reply;
  });
  ipcMain.handle("studio:model-action",(event,request:unknown)=>{
    if(!win||event.sender!==win.webContents||event.senderFrame?.url!==allowedURL||
       event.senderFrame!==win.webContents.mainFrame)return {ok:false,error:"请求来源无效"} satisfies ModelReply;
    return modelAction(request);
  });
  if(smoke){
    ipcMain.handle("studio:smoke-result",(event,value:unknown)=>{
      if(win&&event.sender===win.webContents&&event.senderFrame?.url===allowedURL){
        console.log("studio_smoke="+String(value===true));app.exit(value===true?0:1);
      }
    });
    setTimeout(()=>app.exit(1),90000).unref();
  }
  create();
  app.on("activate",()=>{if(!win)create()});
});
app.on("before-quit",event=>{if(worker.running){event.preventDefault();if(win)dialog.showMessageBoxSync(win,{type:"info",message:"下载执行器仍在运行，请先结束当前任务。"});}});
app.on("window-all-closed",()=>{if(process.platform!=="darwin")app.quit()});
