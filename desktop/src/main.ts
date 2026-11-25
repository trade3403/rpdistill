import {app,BrowserWindow,ipcMain,session} from "electron";
import {spawn} from "node:child_process";
import {join,resolve} from "node:path";
import {homedir} from "node:os";
import {pathToFileURL} from "node:url";
import {SCHEMA,type Reply,type Snapshot} from "./protocol";
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
let win:BrowserWindow|null=null;
function create(){
  win=new BrowserWindow({width:1672,height:941,minWidth:1000,minHeight:650,
    show:!smoke,backgroundColor:"#10141d",title:"RPDistill Studio",
    webPreferences:{preload:join(__dirname,"preload.cjs"),contextIsolation:true,nodeIntegration:false,
      sandbox:true,webSecurity:true,additionalArguments:smoke?["--studio-smoke"]:[]}});
  win.webContents.setWindowOpenHandler(()=>({action:"deny"}));
  win.webContents.on("will-navigate",(e,url)=>{if(url!==allowedURL)e.preventDefault()});
  win.webContents.on("will-attach-webview",e=>e.preventDefault());
  win.on("closed",()=>{win=null});
  void win.loadFile(page);
}
app.whenReady().then(()=>{
  session.defaultSession.setPermissionRequestHandler((_wc,_permission,cb)=>cb(false));
  session.defaultSession.setPermissionCheckHandler(()=>false);
  ipcMain.handle("studio:snapshot",async(event)=>{
    if(!win||event.sender!==win.webContents||event.senderFrame?.url!==allowedURL||
       event.senderFrame!==win.webContents.mainFrame)return {ok:false,error:"请求来源无效"} satisfies Reply;
    return query();
  });
  if(smoke){
    ipcMain.handle("studio:smoke-result",(event,value:unknown)=>{
      if(win&&event.sender===win.webContents&&event.senderFrame?.url===allowedURL){
        console.log("studio_smoke="+String(value===true));app.exit(value===true?0:1);
      }
    });
    setTimeout(()=>app.exit(1),30000).unref();
  }
  create();
  app.on("activate",()=>{if(!win)create()});
});
app.on("window-all-closed",()=>{if(process.platform!=="darwin")app.quit()});
