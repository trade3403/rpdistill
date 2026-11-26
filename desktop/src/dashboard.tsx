import React,{useState} from "react";
import type {Snapshot,ModelRequest,Row} from "./protocol";
import {LossChart} from "./training-center";
export const navigation=["运行控制中心","论文采集中心","教师模型管理","训练数据管理","蒸馏训练任务","模型评测中心","模型导出与发布","任务计划与自动化","系统资源监控","设置与偏好"];
export const views=[0,2,1,2,3,4,4,2,5,6];
const navPaths=[
"M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9",
"M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6",
"M12 2 22 7v10l-10 5-10-5V7zm0 10L2 7m10 5 10-5m-10 5v10",
"M3 5c0-4 18-4 18 0s-18 4-18 0v14c0 4 18 4 18 0V5M3 12c0 4 18 4 18 0",
"M12 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6M5 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6m14 0a3 3 0 1 0 0 6 3 3 0 0 0 0-6M10 9l-3 6m7-6 3 6M8 18h8",
"M3 21h18M5 17v-5m5 5V8m5 9V4m5 13V2",
"M12 2 22 7v10l-10 5-10-5V7zm0 10L2 7m10 5 10-5m-10 5v10",
"M4 5h16v16H4zM4 10h16M8 2v6m8-6v6m-8 7h3m3 0h2",
"M2 12h4l3-8 4 16 3-8h6",
"M9 3h6l1 3 3 1 2 4-2 2v3l-4 4-3-1-3 1-4-4v-3l-2-2 2-4 3-1zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6"];
function NavGlyph({i}:{i:number}){return <svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={navPaths[i]}/></svg>}
const pipeline=["论文检索","论文下载","论文解析","教师翻译","语料清洗","蒸馏训练","评测量化","模型导出"];
const shapes=["M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6","M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5","M5 3h10l4 4v14H5zM14 3v5h5M8 12h8m-8 4h8","M3 5h12M9 2v3m-4 3c1 5 5 8 9 9M13 8c-1 5-5 8-9 10M13 21l4-11 4 11m-7-4h6","M3 4h18l-7 9v7l-4-2v-5z","M9 4a4 4 0 0 0-5 5 4 4 0 0 0 0 7 4 4 0 0 0 5 4V4m6 0a4 4 0 0 1 5 5 4 4 0 0 1 0 7 4 4 0 0 1-5 4V4M12 3v18","M4 20h17M6 16v-6m5 6V5m5 11v-8m5 8V3","M12 2 22 7v10l-10 5-10-5V7zm0 10L2 7m10 5 10-5m-10 5v10"];
function Glyph({i,size=30}:{i:number;size?:number}){return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={shapes[i%shapes.length]}/></svg>}
const display=(v:unknown)=>v==null?"—":typeof v==="number"?v.toLocaleString("zh-CN"):String(v);
const activeStates=["running","pause_requested","cancel_requested"];
const active=(r:Row)=>activeStates.includes(String(r.state));
const fmtBytes=(v:unknown)=>typeof v==="number"?(v/1024**3).toFixed(1)+" GiB":"—";
const labels:Record<string,string>={queued:"排队",running:"运行中",pause_requested:"暂停请求",cancel_requested:"停止请求",paused:"已暂停",cancelled:"已取消",failed:"失败",interrupted:"中断",complete:"训练完成",candidate_complete:"候选已生成",insufficient_candidates:"候选不足",succeeded:"下载完成",budget_exhausted:"预算耗尽"};
export function TopBar({data,stale,refresh,busy}:{data:Snapshot|null;stale:boolean;refresh:()=>Promise<void>;busy:boolean}){
 const running=!!data&&(!!data.counts.pipeline_active||!!data.counts.training_active||!!data.counts.download_active||!!data.local_evaluation_worker?.running||!!data.counts.evaluation_active||!!data.local_environment_worker?.running||!!data.local_asset_worker?.running||!!data.local_worker?.running||!!data.local_training_worker?.running||!!data.local_corpus_worker?.running);
 return <header className="studio-top"><div className="studio-brand"><svg width="48" height="48" viewBox="0 0 48 48" aria-hidden="true"><rect x="1" y="1" width="46" height="46" rx="14" fill="#6236d6"/><path d="m24 8 17 9-17 9-17-9zm-17 16 17 9 17-9M7 31l17 9 17-9" stroke="#fff" strokeWidth="2.4" fill="none" strokeLinejoin="round"/></svg><div><div className="studio-name">RPDistill Studio <span>V{data?.version??"0.1.0"}</span></div><div className="studio-subtitle">全自动科研翻译模型蒸馏工厂</div></div></div><div className="studio-workflow">{["自动采集论文","教师模型翻译","知识蒸馏训练","自动评测量化","导出 RPTranslate 模型"].map((t,i)=><span key={t}><Glyph i={[2,3,5,6,7][i]} size={27}/>{t}</span>)}</div><button className={"studio-status "+(stale?"bad":running?"running":"")} disabled={busy} onClick={()=>void refresh()} title="刷新真实后端状态">{stale?"● 连接异常":!data?"● 连接中":running?"● 任务运行中":"● 后端就绪"}</button></header>
}
export function SideNav({nav,onNavigate}:{nav:number;onNavigate:(n:number)=>void}){return <aside className="studio-nav" aria-label="功能导航">{navigation.map((s,i)=><button key={s} className={"studio-nav-item"+(nav===i?" selected":"")} onClick={()=>onNavigate(i)} aria-current={nav===i?"page":undefined}><span aria-hidden="true"><NavGlyph i={i}/></span>{s}</button>)}</aside>}
function PanelConfig({data,stale,refresh,onNavigate}:{data:Snapshot|null;stale:boolean;refresh:()=>Promise<void>;onNavigate:(i:number)=>void}){
 const teachers=(["huggingface","modelscope"] as const).flatMap(source=>(data?.rows[source==="huggingface"?"teachers":"modelscope_teachers"]??[]).map(row=>({source,row,key:source+":"+row.model_id+":"+row.revision})));
 const [teacherKey,setTeacher]=useState(""),[keyword,setKeyword]=useState(""),[start,setStart]=useState(""),[end,setEnd]=useState(""),[limit,setLimit]=useState("20"),[budget,setBudget]=useState(""),[approved,setApproved]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
 const teacher=teachers.find(t=>t.key===teacherKey);
 const running=!!data&&(!!data.counts.pipeline_active||!!data.counts.training_active||!!data.counts.download_active||!!data.local_evaluation_worker?.running||!!data.counts.evaluation_active||!!data.local_environment_worker?.running||!!data.local_asset_worker?.running||!!data.local_worker?.running||!!data.local_training_worker?.running||!!data.local_corpus_worker?.running);
 const locked=busy||stale||!data||running;
 const bytes=Number(budget)*1024**2,number=Number(limit);
 const ready=!!teacher&&!!teacher.row.license&&keyword.trim().length>0&&!!start&&!!end&&start<=end&&Number.isInteger(number)&&number>=1&&number<=50&&Number.isSafeInteger(bytes)&&bytes>0&&bytes<=2**40&&approved;
 const training=data?.rows.training?.filter(active)??[],downloads=data?.rows.downloads?.filter(active)??[];
 const target=training.length===1&&data?.counts.training_active===1&&!data.counts.download_active&&!data.counts.pipeline_active?{type:"training",row:training[0]}:downloads.length===1&&data?.counts.download_active===1&&!data.counts.training_active&&!data.counts.pipeline_active?{type:"download",row:downloads[0]}:null;
 const editable=!!target&&!busy&&!stale;
 function update(f:()=>void){f();setApproved(false)}
 async function launch(){
  if(!teacher||!ready||locked)return;setBusy(true);setApproved(false);setMessage("");
  try{
   const created=await window.studio.modelAction({kind:"pipeline-create",source:teacher.source,model_id:String(teacher.row.model_id),revision:String(teacher.row.revision),keyword,start_date:start,end_date:end,device:"cpu",dtype:"float32",search_limit:number,paper_limit:number,segment_limit:1000,max_bytes:bytes,approved:true});
   if(!created.ok){setMessage(created.error);return}
   const row=created.data as {id?:string};
   if(typeof row?.id!=="string"||! /^[a-f0-9]{32}$/.test(row.id)){setMessage("任务已创建，请在语料中心核对并启动");return}
   const launched=await window.studio.modelAction({kind:"pipeline-run",id:row.id,approved:true});
   setMessage(launched.ok?"单次语料执行器已启动，候选数据仍需复核":"已创建任务；启动失败："+launched.error);
  }catch{setMessage("操作异常，请核对已保存任务，避免重复创建")}finally{await refresh();setBusy(false)}
 }
 async function control(kind:"pause"|"cancel"){
  if(!target||!editable)return;
  if(kind==="cancel"&&!window.confirm("确认请求停止当前"+(target.type==="training"?"训练":"下载")+"任务？"))return;
  setBusy(true);setMessage("");
  const id=String(target.row.id);
  const req:ModelRequest=target.type==="training"?{kind:kind==="pause"?"training-pause":"training-cancel",id}:{kind,id};
  try{const result=await window.studio.modelAction(req);setMessage(result.ok?"已请求控制，以后端实际状态为准":result.error)}catch{setMessage("操作失败，请核对任务状态")}finally{await refresh();setBusy(false)}
 }
 return <section className="config-panel studio-config" aria-label="自动化任务配置">
 <h2><NavGlyph i={9}/> 自动化任务配置 <small>（单次语料）</small></h2>
 <div className="config-content">
 <div className="config-line"><span>运行模式</span><div className="config-mode"><button className="chosen" type="button" disabled={locked}>单次语料</button><button disabled title="持续模式未实现">∞ 持续自动蒸馏</button></div></div>
 <label className="config-line"><span>科研关键词</span><input placeholder="英文科研主题" value={keyword} maxLength={200} disabled={locked} onChange={e=>update(()=>setKeyword(e.target.value))}/></label>
 <div className="config-line"><span>论文来源</span><div className="source-grid">{["arXiv","NCBI PMC","Europe PMC","OpenAlex","Crossref","Unpaywall"].map(t=><label key={t}><input type="checkbox" checked={t==="NCBI PMC"} disabled readOnly/>{t}</label>)}</div></div>
 <label className="config-line"><span>采集数量</span><input type="number" min="1" max="50" value={limit} disabled={locked} onChange={e=>update(()=>setLimit(e.target.value))}/></label>
 <label className="config-line"><span>发表起始</span><input type="date" value={start} disabled={locked} onChange={e=>update(()=>setStart(e.target.value))}/></label>
 <label className="config-line"><span>发表截止</span><input type="date" value={end} disabled={locked} onChange={e=>update(()=>setEnd(e.target.value))}/></label>
 <label className="config-line"><span>教师模型</span><select value={teacherKey} disabled={locked} onChange={e=>update(()=>setTeacher(e.target.value))}><option value="">选择已登记模型</option>{teachers.map(t=><option key={t.key} value={t.key}>{t.row.model_id} · {t.source} · {String(t.row.revision).slice(0,8)}</option>)}</select></label>
 <label className="config-line"><span>学生模型</span><input value="RPTranslate Marian" readOnly disabled/></label>
 <h3>训练资源预算 <small>ⓘ</small></h3>
 <label className="config-line"><span>全文下载 (MiB)</span><input type="number" min="1" max="1048576" placeholder="必填预算" value={budget} disabled={locked} onChange={e=>update(()=>setBudget(e.target.value))}/></label>
 <div className="config-line"><span>最大训练时长</span><button className="config-link" onClick={()=>onNavigate(4)}>在训练中心配置 ›</button></div>
 <div className="config-line"><span>最大 GPU 显存</span><button className="config-link" onClick={()=>onNavigate(4)}>在训练中心配置 ›</button></div>
 <div className="config-line"><span>检查点磁盘</span><button className="config-link" onClick={()=>onNavigate(4)}>{fmtBytes(data?.student_resources?.checkpoint_free_bytes)} 可用 ›</button></div>
 <h3>自动化策略</h3><div className="strategy-grid">{["自动增量采集新论文","质量达标后评测","达标后自动量化导出","失败自动重试与续传"].map(s=><label key={s}><input type="checkbox" disabled/>{s}</label>)}</div>
 <p className="config-hint">当前仅单次 NCBI PMC → 教师翻译 → 候选数据集（CPU FP32）。持续调度、自动训练及发布尚未接入；采集使用共享论文目录。</p>
 <label className="config-approve"><input type="checkbox" checked={approved} disabled={locked} onChange={e=>setApproved(e.target.checked)}/>确认教师许可、用途和本次采集预算</label>
 {message&&<div role="status" className="config-message">{message}</div>}
 </div><div className="config-actions"><button disabled={locked||!ready} onClick={()=>void launch()}>▶ 一键启动单次语料流水线</button><div><button disabled={!editable||target?.row.state!=="running"} onClick={()=>void control("pause")}>Ⅱ 暂停</button><button disabled={!editable||!["running","pause_requested"].includes(String(target?.row.state))} onClick={()=>void control("cancel")}>■ 停止</button></div></div>
 <small className="config-hint">暂停 / 停止仅适用于唯一活动下载或训练任务；语料不支持协作暂停。</small></section>
}
export function Dashboard({data,stale,refresh,onNavigate}:{data:Snapshot|null;stale:boolean;refresh:()=>Promise<void>;onNavigate:(i:number)=>void}){
 const [monitor,setMonitor]=useState(0),[gpuIndex,setGpuIndex]=useState(0),[autoScroll,setAutoScroll]=useState(true),[hiddenBefore,setHiddenBefore]=useState(0);
 const logRef=React.useRef<HTMLDivElement>(null);
 const c=data?.counts,r=data?.rows;
 const corpus=r?.pipelines?.find(x=>x.state==="running")??r?.pipelines?.[0],train=r?.training?.find(active),download=r?.downloads?.find(active);
 const liveCorpus=corpus?.state==="running",stage=typeof corpus?.stage==="number"?corpus.stage:0;
 const phase=(i:number)=>!stale&&corpus&&i<5?(i<stage?"done":i===stage&&liveCorpus?"active":"waiting"):!stale&&i===5&&train?"active":"waiting";
 const samples=r?.training_loss??[];const metric=samples[samples.length-1];
 const steps=metric&&metric.job_id===train?.id&&typeof metric.step==="number"?metric.step:train?.step;
 const target=train?.target_steps;
 const rate=metric&&metric.job_id===train?.id&&typeof metric.seconds==="number"&&metric.seconds>0&&typeof metric.created==="string"&&Date.now()-Date.parse(metric.created)<30000?1/metric.seconds:null;
 const eta=rate&&typeof target==="number"&&typeof steps==="number"?Math.ceil(Math.max(0,target-steps)/rate):null;
 const cards=[["已采集论文",display(c?.papers),"本地论文目录"],["候选语料",display(c?.pairs),"双语候选 · 待复核"],["训练步数",train?display(steps)+" / "+display(target):"—","优化器步 · 当前任务"],["当前模型",display(train?"RPTranslate Marian":liveCorpus?corpus?.model_id:download?.model_id??null),train?"学生训练":"教师模型 / 下载"],["预计完成",eta===null?"—":display(eta)+" 秒","仅计算时间估算"]];
 const gpu=data?.devices.nvidia?.devices?.find(g=>g.index===gpuIndex)??data?.devices.nvidia?.devices?.[0];
 const percent=gpu&&gpu.total_mib>0?Math.round(100*(gpu.total_mib-gpu.free_mib)/gpu.total_mib):null;
 const logs=[...(r?.training_events??[]).map(x=>({time:String(x.created??""),line:"训练 "+String(x.job_id).slice(0,12)+" · "+(labels[String(x.state)]??x.state)+(x.step!=null?" · 步数 "+x.step:"")+(x.error?" · "+x.error:""),error:!!x.error})),...(r?.pipelines??[]).map(x=>({time:String(x.updated??""),line:"语料 "+display(x.keyword)+" · "+(labels[String(x.state)]??x.state)+" · 已提交阶段 "+display(x.stage)+"/5"+(x.error?" · "+x.error:""),error:!!x.error})),...(r?.downloads??[]).map(x=>({time:String(x.updated??""),line:"下载 "+display(x.model_id)+" · "+(labels[String(x.state)]??x.state)+(x.error?" · "+x.error:""),error:!!x.error}))].sort((a,b)=>a.time.localeCompare(b.time)).slice(-100);
 const visible=logs.filter(x=>Date.parse(x.time)>hiddenBefore);
 React.useEffect(()=>{if(autoScroll&&logRef.current)logRef.current.scrollTop=logRef.current.scrollHeight},[autoScroll,data,hiddenBefore]);
 const bars=[["GPU 利用率",gpu?.utilization_percent,100,"%"],["显存占用",percent,100,"%"],["GPU 温度",gpu?.temperature_c,100,"°C"],["功耗",gpu?.power_w,null,"W"]] as const;
 return <><div className="studio-dashboard">
 <section className="panel flow-panel"><h2><Glyph i={2} size={23}/> 全自动蒸馏流水线 <small>（真实阶段 · 单次语料与训练独立授权）</small></h2><div className="studio-pipeline">{pipeline.map((name,i)=><div key={name} className={"flow-stage "+phase(i)}><Glyph i={i}/><b>{name}</b><small>{phase(i)==="done"?"✓ 已提交":phase(i)==="active"?"◉ 进行中":i>=6?"待接入":"等待中"}</small></div>)}</div></section>
 <section className="studio-metrics">{cards.map(([name,val,sub],i)=><article key={name} className="metric"><span><Glyph i={[7,2,5,7,6][i]} size={24}/>{name}</span><strong title={val}>{val}</strong><small>{sub}</small>{i===2&&typeof steps==="number"&&typeof target==="number"&&target>0&&<div className="metric-progress"><progress max={target} value={steps}/><small>{Math.min(100,Math.round(steps/target*100))}%</small></div>}</article>)}</section>
 <section className="studio-monitors"><article className="panel loss-panel"><h2><Glyph i={6} size={23}/> 训练过程监控</h2><div className="monitor-tabs">{["Loss 曲线","评测指标","GPU/显存","训练速度"].map((s,i)=><button className={monitor===i?"selected":""} key={s} onClick={()=>setMonitor(i)}>{s}</button>)}</div>{monitor===0?<LossChart data={data}/>:monitor===1?<div className="empty">{r?.evaluations?.find(x=>x.state==="complete")?<>最新已完成报告 · BLEU {display(r.evaluations.find(x=>x.state==="complete")?.bleu)} · chrF {display(r.evaluations.find(x=>x.state==="complete")?.chrf)} · 非发布批准</>:"暂无评测报告，未判定质量通过"}</div>:monitor===2?<div className="empty">显存 {gpu?display(gpu.total_mib-gpu.free_mib)+" / "+display(gpu.total_mib)+" MiB":"—"}</div>:<div className="empty">当前 {rate===null?"—":rate.toFixed(2)+" 步/秒"} · 计算剩余 {eta===null?"—":eta+" 秒"}</div>}</article>
 <article className="panel studio-gpu"><h2><Glyph i={5} size={23}/> GPU 资源监控 <small>{gpu?.name??"未检测到 GPU"}</small></h2>{(data?.devices.nvidia?.devices?.length??0)>1&&<select value={gpu?.index??0} onChange={e=>setGpuIndex(Number(e.target.value))}>{data?.devices.nvidia.devices.map(g=><option key={g.index} value={g.index}>{g.name}</option>)}</select>}<div className="gpu-layout"><div><div className="gpu-ring" style={{background:percent===null?"#26354b":"conic-gradient(#24b7ef 0%,#24d8a5 "+percent+"%,#26354b "+percent+"%,#26354b 100%)"}}><div><strong>{percent===null?"—":percent+"%"}</strong><small>显存使用</small></div></div><p>{gpu?((gpu.total_mib-gpu.free_mib)/1024).toFixed(1)+" / "+(gpu.total_mib/1024).toFixed(1)+" GiB":"无硬件记录"}</p></div><div className="gpu-bars">{bars.map(([label,v,max,unit],i)=><div key={label}><span>{label}<b>{v==null?"—":display(v)+" "+unit}</b></span>{max!==null&&<div className={"resource-track color-"+i}><i style={{width:v==null?"0%":Math.min(100,Math.max(0,v/max*100))+"%"}}/></div>}{max===null&&<small>未取得功耗上限</small>}</div>)}</div></div></article></section>
 <section className="panel studio-logs"><h2><Glyph i={2} size={23}/> 实时运行日志 <span><label><input type="checkbox" checked={autoScroll} onChange={e=>setAutoScroll(e.target.checked)}/>自动滚动</label><button onClick={()=>setHiddenBefore(Date.now())}>清空显示</button></span></h2><div ref={logRef} className="log-body">{visible.length?visible.map((l,i)=><div key={l.time+i}><span>[{l.time.slice(0,19).replace("T"," ")}]</span> <b className={l.error?"log-error":""}>[{l.error?"ERROR":"INFO"}]</b> {l.line}</div>):<p>暂无可显示的真实任务记录 · 清空仅影响当前视图</p>}</div></section>
 </div><PanelConfig data={data} stale={stale} refresh={refresh} onNavigate={onNavigate}/>
 <footer className="studio-footer"><span className={stale?"bad":liveCorpus||train||download?"running":""}>● {stale?"快照过期":liveCorpus||train||download?"任务运行中":"待机"}</span><span>全自动科研论文采集 → 翻译语料生成 → 知识蒸馏训练 → 评测量化 → 导出</span><span>当前阶段：{liveCorpus?pipeline[stage]??"语料任务":train?"蒸馏训练":download?"模型下载":"—"}</span>{data?.environment?.deploy_available&&(data.environment.source==="base"||data.environment.degraded)?<button className="config-link" onClick={()=>onNavigate(9)}>配置 / 修复训练环境 ›</button>:<span>运行时长：—</span>}<span>计算剩余：{eta===null?"—":eta+" 秒"}</span></footer></>
}
