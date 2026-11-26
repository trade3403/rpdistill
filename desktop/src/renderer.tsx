import React,{useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import type {Snapshot,Row} from "./protocol";
import {ModelCenter} from "./model-center";
import {CorpusCenter} from "./corpus-center";
import {TrainingCenter,LossChart} from "./training-center";
import {Dashboard,SideNav,TopBar,navigation,views} from "./dashboard";
import {EvaluationCenter} from "./evaluation-center";
import {ArtifactCenter} from "./artifact-center";
const tabs=["工作台","模型与下载","科研语料","训练任务","评测与导出"];
const stages=["论文发现","合法全文","语料分段","教师译文","候选数据集","学生训练","质量评测","模型导出"];
const size=(n:unknown)=>typeof n==="number"?(n/1024**3).toFixed(2)+" GiB":"—";
const value=(v:unknown)=>v===null||v===undefined?"—":String(v);
function Table({rows,fields}:{rows:Row[];fields:[string,string][]}){
 return rows.length?<div className="table-scroll"><table><thead><tr>{fields.map(([k,l])=><th key={k}>{l}</th>)}</tr></thead><tbody>
 {rows.map((r,i)=><tr key={String(r.id??r.model_id??i)+i}>{fields.map(([k])=><td key={k} title={value(r[k])}>{value(r[k])}</td>)}</tr>)}
 </tbody></table></div>:<div className="empty">暂无记录</div>
}
function TaskConfig({data}:{data:Snapshot|null}){
 const teachers=[...(data?.rows.teachers??[]),...(data?.rows.modelscope_teachers??[])];
 const gpus=data?.devices.nvidia?.devices??[];
 return <section className="config-panel" aria-label="任务配置">
  <div className="config-title"><h2>任务配置</h2><span className="tag">只读预览</span></div>
  <p className="muted">当前仅监控；配置保存和任务控制将在后续阶段接入。</p>
  <fieldset disabled><legend>模型配置</legend>
  <label>教师模型<select defaultValue=""><option value="">请选择已登记模型</option>{teachers.map((m,i)=><option key={i} value={String(i)}>{value(m.model_id)}</option>)}</select></label>
  <label>学生模型<input value="RPTranslate" readOnly/></label>
  </fieldset>
  <fieldset disabled><legend>采集与训练</legend>
  <label>论文关键词<input placeholder="尚未配置"/></label>
  <label>运行模式<div className="mode-options"><label><input type="radio" name="mode"/> 单次</label><label><input type="radio" name="mode"/> 持续</label></div></label>
  <label>训练设备<select defaultValue=""><option value="">尚未选择</option>{gpus.map(g=><option key={g.index} value={g.index}>{g.name}</option>)}</select></label>
  </fieldset>
  <fieldset disabled><legend>资源预算</legend>
  <label>下载 / 磁盘预算<input placeholder="尚未配置"/></label>
  <label>训练时长 / 显存预算<input placeholder="尚未配置"/></label>
  </fieldset>
  <div className="config-actions"><button disabled>▶ 启动自动蒸馏</button><div><button disabled>Ⅱ 暂停</button><button disabled>■ 停止</button></div></div>
  <p className="muted">未接入的操作保持禁用，不触发后端任务。</p>
 </section>
}
function MonitorPanels({data}:{data:Snapshot|null}){
 const d=data?.devices;
 const errors=[...(data?.rows.downloads??[]),...(data?.rows.pipelines??[]),...(data?.rows.training??[])].filter(r=>r.error);
 return <>
  <section className="monitor-grid">
   <article className="panel loss-panel"><div className="panel-heading"><h2>训练 Loss 曲线</h2><small>优化器步采样</small></div>
   <LossChart data={data}/></article>
   <article className="panel gpu-panel"><div className="panel-heading"><h2>GPU 监控</h2><small>真实硬件快照</small></div>
   {d?.nvidia?.devices?.length?d.nvidia.devices.map(g=><div className="gpu-card" key={g.index}><b>{g.name}</b><small>显存已用 {g.total_mib-g.free_mib} / {g.total_mib} MiB</small>{g.total_mib>0&&g.free_mib>=0&&g.free_mib<=g.total_mib&&<meter min={0} max={g.total_mib} value={g.total_mib-g.free_mib}/>}<small>GPU 利用率：{g.utilization_percent==null?"—":g.utilization_percent+"%"} · 温度：{g.temperature_c==null?"—":g.temperature_c+" °C"} · 功耗：{g.power_w==null?"—":g.power_w+" W"}</small></div>):<div className="empty">尚无 NVIDIA GPU 记录 · {d?.nvidia?.status??"未取得快照"}</div>}
   <div className="monitor-hardware"><span>CPU <b>{value(d?.logical_cpus)} 核</b></span><span>内存 <b>{size(d?.memory_bytes)}</b></span></div></article>
  </section>
  <section className="panel log-panel"><div className="panel-heading"><h2>任务日志</h2><small>最近任务错误摘要</small></div>{errors.length?<Table rows={errors} fields={[["updated","更新时间"],["id","任务 ID"],["error","错误摘要"]]}/>:<div className="log-empty">暂无已读取的任务错误 · 实时事件流尚未接入</div>}</section>
 </>
}
function App(){
 const [data,setData]=useState<Snapshot|null>(null),[error,setError]=useState(""),[nav,setNav]=useState(0),[busy,setBusy]=useState(false);
 const tab=views[nav];
 async function refresh(){setBusy(true);try{const r=await window.studio.snapshot();if(r.ok){setData(r.data);setError("")}else setError(r.error)}
 catch{setError("无法连接桌面后端")}finally{setBusy(false)}}
 useEffect(()=>{void refresh();const id=setInterval(()=>void refresh(),tab===4?10000:3000);return()=>clearInterval(id)},[tab]);
 const c=data?.counts,r=data?.rows,d=data?.devices;
 const counts=[["登记教师模型",c?c.teachers+c.modelscope_teachers:undefined],["科研论文",c?.papers],["已存全文",c?.fulltexts],["语料分段",c?.segments],["双语候选",c?.pairs],["数据集版本",c?.datasets]];
 const smokeStarted=React.useRef(false);
 useEffect(()=>{if(data&&!smokeStarted.current&&typeof (window as any).studioSmoke==="function"){
 smokeStarted.current=true;const ok=data.schema==="rpdistill-studio-snapshot-v1"&&data.read_only===true&&typeof (window as any).require==="undefined"&&document.querySelectorAll(".metric").length===5&&document.querySelectorAll(".flow-stage").length===8&&document.querySelectorAll(".studio-nav-item").length===10&&document.querySelector(".config-panel")!==null&&document.querySelector(".loss-panel")!==null&&document.querySelectorAll(".config-actions button:disabled").length===3&&data.counts.downloads===1&&document.body.textContent?.includes("fixture/model")===true;
 const id=String(data.rows.downloads?.[0]?.id);
 void (async()=>{try{
  const invalid=await window.studio.modelAction({kind:"pause",id:"--help"});
  const unapproved=await window.studio.modelAction({kind:"enqueue",source:"huggingface",model_id:"fixture/second",revision:"b".repeat(40),license:"apache-2.0",max_bytes:1024,reviewed:false});
  const paused=await window.studio.modelAction({kind:"pause",id});
  const p=await window.studio.snapshot();
  const resumed=await window.studio.modelAction({kind:"resume",id});
  const enqueued=await window.studio.modelAction({kind:"enqueue",source:"huggingface",model_id:"fixture/second",revision:"b".repeat(40),license:"apache-2.0",max_bytes:1024,reviewed:true});
  const q=await window.studio.snapshot();
  const queueOK=q.ok&&q.data.counts.downloads===2&&q.data.rows.downloads.every(r=>r.state==="queued");
  // Offline smoke: cancel fixtures, run actual empty CLI queue in a native child.
  const removed=q.ok?await Promise.all([]).then(async()=>{for(const row of q.data.rows.downloads){const result=await window.studio.modelAction({kind:"cancel",id:String(row.id)});if(!result.ok)return false}return true}):false;
  const badStart=await window.studio.modelAction({kind:"worker-start",unexpected:true} as any);
  const started=await window.studio.modelAction({kind:"worker-start"});
  const duplicate=await window.studio.modelAction({kind:"worker-start"});
  let final=await window.studio.snapshot();
  for(let i=0;i<30&&final.ok&&final.data.local_worker?.running;i++){await new Promise(resolve=>setTimeout(resolve,250));final=await window.studio.snapshot()}
  const request={kind:"pipeline-create" as const,source:"huggingface" as const,model_id:"fixture/model",revision:"a".repeat(40),keyword:"cell biology",start_date:"2024-01-01",end_date:"2024-12-31",device:"cpu",dtype:"float32",search_limit:10,paper_limit:2,segment_limit:20,max_bytes:1024,approved:true};
  const denied=await window.studio.modelAction({...request,approved:false});
  const created=await window.studio.modelAction(request);
  const rejected=await window.studio.modelAction({kind:"pipeline-run",id:"0".repeat(32),approved:false});
  const launch=await window.studio.modelAction({kind:"pipeline-run",id:"0".repeat(32),approved:true});
  let corpusState=await window.studio.snapshot();
  for(let i=0;i<30&&corpusState.ok&&corpusState.data.local_corpus_worker?.running;i++){await new Promise(resolve=>setTimeout(resolve,250));corpusState=await window.studio.snapshot()}
  const corpusOK=!denied.ok&&created.ok&&!rejected.ok&&launch.ok&&corpusState.ok&&corpusState.data.local_corpus_worker?.running===false&&corpusState.data.local_corpus_worker.message==="语料执行器退出异常，请核对持久任务状态"&&corpusState.data.counts.pipelines===1&&corpusState.data.rows.pipelines[0]?.state==="queued";
  const train={kind:"training-enqueue" as const,version:"c".repeat(64),license:"apache-2.0",steps:2,batch_size:1,learning_rate:0.0001,accumulation:1,device:"cpu",precision:"float32",cuda_bytes:0,segment_steps:1,segment_seconds:60,total_seconds:120,checkpoint_bytes:1073741824,total_checkpoint_bytes:2147483648,approved:true};
  const rejectedTrain=await window.studio.modelAction({...train,approved:false});
  const createdTrain=await window.studio.modelAction(train);
  const trainSnapshot=await window.studio.snapshot();
  const trainId=trainSnapshot.ok?String(trainSnapshot.data.rows.training[0]?.id):"";
  const trainPaused=await window.studio.modelAction({kind:"training-pause",id:trainId});
  const trainResumed=await window.studio.modelAction({kind:"training-resume",id:trainId});
  const trainCancelled=await window.studio.modelAction({kind:"training-cancel",id:trainId});
  const deniedTrainStart=await window.studio.modelAction({kind:"training-start",approved:false});
  const trainStarted=await window.studio.modelAction({kind:"training-start",approved:true});
  let trainFinal=await window.studio.snapshot();
  for(let i=0;i<30&&trainFinal.ok&&trainFinal.data.local_training_worker?.running;i++){await new Promise(resolve=>setTimeout(resolve,250));trainFinal=await window.studio.snapshot()}
  const trainOK=!rejectedTrain.ok&&createdTrain.ok&&trainPaused.ok&&trainResumed.ok&&trainCancelled.ok&&!deniedTrainStart.ok&&trainStarted.ok&&trainFinal.ok&&trainFinal.data.local_training_worker?.running===false&&trainFinal.data.local_training_worker.message==="没有待训练任务"&&trainFinal.data.rows.training[0]?.state==="cancelled";
  const deniedAssets=await window.studio.modelAction({kind:"student-assets",approved:false});
  const injectedAssets=await window.studio.modelAction({kind:"student-assets",approved:true,root:"C:/unexpected"} as any);
  const assetsOK=!deniedAssets.ok&&!injectedAssets.ok&&trainFinal.ok&&trainFinal.data.student_resources?.state==="missing"&&trainFinal.data.student_resources.file_count===5&&trainFinal.data.local_asset_worker?.running===false;
  const geometryOK=window.innerWidth===1672&&window.innerHeight===941&&[".studio-top",".studio-nav",".flow-panel",".studio-metrics",".studio-monitors",".studio-logs",".studio-config",".studio-footer"].every(selector=>{const element=document.querySelector(selector);if(!element)return false;const b=element.getBoundingClientRect();return b.width>0&&b.height>0&&b.left>=0&&b.top>=0&&b.right<=window.innerWidth+1&&b.bottom<=window.innerHeight+1});
  const deniedEval=await window.studio.modelAction({kind:"evaluate-job",id:"a".repeat(32),review_note:"fixture",approved:false});
  const injectedEval=await window.studio.modelAction({kind:"evaluate-job",id:"a".repeat(32),review_note:"fixture",approved:true,input:"C:/unexpected"} as any);
  const deniedArtifact=await window.studio.modelAction({kind:"artifact-run",id:"a".repeat(32),mode:"int8",max_bytes:2**30,max_seconds:60,license_label:"",rights_note:"",approved:false});
  const injectedArtifact=await window.studio.modelAction({kind:"artifact-run",id:"a".repeat(32),mode:"int8",max_bytes:2**30,max_seconds:60,license_label:"",rights_note:"",approved:true,root:"C:/unexpected"} as any);
  const deniedReview=await window.studio.modelAction({kind:"review-run",id:"a".repeat(32),mode:"rust",timeout_seconds:180,approved:false});
  const injectedReview=await window.studio.modelAction({kind:"review-run",id:"a".repeat(32),mode:"rust",timeout_seconds:180,approved:true,executable:"C:/unexpected.exe"} as any);
  (window as any).studioSmoke(!deniedReview.ok&&!injectedReview.ok&&!deniedArtifact.ok&&!injectedArtifact.ok&&!deniedEval.ok&&!injectedEval.ok&&geometryOK&&assetsOK&&trainOK&&corpusOK&&ok&&!invalid.ok&&!unapproved.ok&&paused.ok&&p.ok&&p.data.rows.downloads[0]?.state==="paused"&&resumed.ok&&enqueued.ok&&queueOK&&removed&&!badStart.ok&&started.ok&&!duplicate.ok&&final.ok&&final.data.local_worker?.running===false&&final.data.local_worker.message==="没有待下载任务"&&final.data.counts.download_queued===0&&final.data.rows.downloads.every(r=>r.state==="cancelled"));
 }catch{(window as any).studioSmoke(false)}})();
 }},[data]);
 if(tab===0)return <div className="studio-shell"><TopBar data={data} stale={!!error} refresh={refresh} busy={busy}/><SideNav nav={nav} onNavigate={setNav}/><Dashboard data={data} stale={!!error} refresh={refresh} onNavigate={setNav}/></div>;
 return <div className="shell"><aside><div className="brand"><span className="logo">RP</span><div>RPDistill<span>STUDIO · 知识蒸馏</span></div></div>
 <div className="navlabel">工作空间</div>{navigation.map((t,i)=><button className={nav===i?"nav active":"nav"} onClick={()=>setNav(i)} key={t}>{t}</button>)}
 <div className="aside-bottom">本地工作空间<br/><small>本地工作台 · E11c3c</small></div></aside>
 <main><header><div><div className="eyebrow">RPTRANSLATE / 自主模型训练</div><h1>{navigation[nav]}</h1></div><div className="header-actions"><span className={error?"status bad":"status"}>{error?"连接异常":data?"本地后端已连接":"正在连接"}</span><button className="refresh" onClick={()=>void refresh()} disabled={busy}>{busy?"刷新中…":"刷新状态"}</button></div></header>
 {error&&<div role="alert" className="error">{error}；现有数据显示为上次成功快照。</div>}
 <div className="subline">本地真实记录 · {data?.observed_at?new Date(data.observed_at).toLocaleString():"尚未取得快照"}{data&&!data.database_exists?" · 尚无任务数据库":""}</div>
 {tab===3&&<TrainingCenter data={data} refresh={refresh} stale={!!error}/>}

 {tab===1&&<ModelCenter rows={r?.downloads??[]} refresh={refresh} worker={data?.local_worker} queued={c?.download_queued} active={c?.download_active} stale={!!error}/>}

 {tab===1&&<section className="panel"><h2>已登记教师模型</h2><h3>Hugging Face</h3><Table rows={r?.teachers??[]} fields={[["model_id","模型"],["revision","固定版本"],["license","许可"]]}/><h3>ModelScope</h3><Table rows={r?.modelscope_teachers??[]} fields={[["model_id","模型"],["revision","固定版本"],["license","许可"]]}/></section>}
 {tab===2&&<><section className="metrics">{counts.slice(1).map(([label,n])=><article className="metric" key={String(label)}><span>{label}</span><strong>{value(n)}</strong></article>)}</section><CorpusCenter data={data} refresh={refresh} stale={!!error}/><section className="panel"><h2>论文目录 <small>最近 50 项 · 元数据非训练授权</small></h2><Table rows={r?.papers??[]} fields={[["pmcid","PMC ID"],["title","标题"],["publication_date","发表日期"],["eligibility","许可初筛"]]}/></section><section className="panel"><h2>候选数据集 <small>尚未授权训练</small></h2><Table rows={r?.datasets??[]} fields={[["version","版本 SHA"],["model_id","教师"],["train","训练"],["validation","验证"],["test","测试"],["status","状态"]]}/></section></>}
 {tab===6&&<section className="panel"><h2>设置与偏好</h2><p>当前使用本地 Python 与可信启动环境配置，图形化持久偏好尚未接入。</p></section>}
 {tab===4&&(nav===6?<ArtifactCenter data={data} refresh={refresh} stale={!!error}/>:<EvaluationCenter data={data} refresh={refresh} stale={!!error}/>)}
 <section className="panel hardware"><h2>本地硬件</h2><div className="hardware-grid"><div><span>处理器</span><strong>{value(d?.logical_cpus)} 逻辑核心</strong><small>{d?.platform} {d?.architecture}</small></div><div><span>系统内存</span><strong>{size(d?.memory_bytes)}</strong></div><div><span>磁盘可用</span><strong>{size(d?.disk?.free_bytes)}</strong></div><div><span>NVIDIA GPU</span><strong>{d?.nvidia?.devices?.length??"—"} 张</strong><small>{d?.nvidia?.status??"未检测"}</small></div></div>{d?.nvidia?.devices?.map(g=><div className="gpu" key={g.index}>{g.name} · {g.free_mib} / {g.total_mib} MiB 空闲</div>)}<p className="muted">硬件识别不代表 CUDA 训练就绪。</p></section>
 <footer>RPDistill Studio {data?.version??""} · 模型、单次语料及训练队列控制 · 持续自动化待接入</footer>
 </main></div>
}
createRoot(document.getElementById("root")!).render(<App/>);
