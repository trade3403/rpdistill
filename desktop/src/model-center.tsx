import React,{useState} from "react";
import type {ModelSource,ModelRequest,Row,WorkerStatus} from "./protocol";
type Candidate={model_id:string;revision:string|null;license:string|null;restricted:boolean};
function candidates(data:unknown):Candidate[]{
 if(!Array.isArray(data))throw Error("search");
 return data.filter(c=>c&&typeof c.model_id==="string").slice(0,20).map(c=>({model_id:c.model_id,
 revision:typeof c.revision==="string"?c.revision:null,license:typeof c.license==="string"?c.license:null,restricted:!!(c.private||c.gated)}));
}
const fmt=(v:unknown)=>typeof v==="number"?v.toLocaleString("zh-CN"):"—";
const labels:Record<string,string>={queued:"排队中",running:"下载中",pause_requested:"暂停请求中",cancel_requested:"取消请求中",paused:"已暂停",cancelled:"已取消",failed:"失败",interrupted:"中断",completed:"已完成",succeeded:"已完成"};
export function ModelCenter({rows,refresh,worker,queued,active,stale}:{rows:Row[];refresh:()=>Promise<void>;worker?:WorkerStatus;queued?:number;active?:number;stale:boolean}){
 const [source,setSource]=useState<ModelSource>("huggingface"),[query,setQuery]=useState(""),[results,setResults]=useState<Candidate[]>([]);
 const [selected,setSelected]=useState<Candidate|null>(null),[revision,setRevision]=useState(""),[license,setLicense]=useState(""),[budget,setBudget]=useState(""),[reviewed,setReviewed]=useState(false);
 const [recoverId,setRecoverId]=useState<string|null>(null);
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState(""),[revisions,setRevisions]=useState("");
 function reset(){setSelected(null);setRevision("");setLicense("");setBudget("");setReviewed(false);setRevisions("");setResults([])}
 async function execute(request:ModelRequest,success:(data:unknown)=>void|Promise<void>){
  setBusy(true);setMessage("");setError("");
  try{const reply=await window.studio.modelAction(request);if(reply.ok){await success(reply.data)}else setError(reply.error)}
  catch{setError("模型操作连接失败；请刷新队列状态")}finally{setBusy(false)}
 }
 function choose(c:Candidate){setSelected(c);setRevision(c.revision??"");setLicense(c.license??"");setBudget("");setReviewed(false);setRevisions("")}
 const bytes=Number(budget)*1024**3;
 const ready=!!selected&&!selected.restricted&&/^[a-f0-9]{40}$/.test(revision)&&/^[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}$/.test(license)&&Number.isSafeInteger(bytes)&&bytes>0&&reviewed;
 return <>
 <section className="panel model-center"><h2>教师模型在线搜索</h2>
 <p className="muted">需要联网及对应 SDK：python -m pip install -e ".[hub,modelscope]"。搜索不下载模型。</p>
 <form className="model-search" onSubmit={e=>{e.preventDefault();reset();void execute({kind:"search",source,query},data=>{setResults(candidates(data));setMessage("搜索完成，许可及可下载性仍需核验。")})}}>
 <label>模型来源<select value={source} disabled={busy} onChange={e=>{setSource(e.target.value as ModelSource);reset()}}><option value="huggingface">Hugging Face</option><option value="modelscope">ModelScope</option></select></label>
 <label>模型关键词<input value={query} disabled={busy} maxLength={100} placeholder="例如 Qwen" onChange={e=>setQuery(e.target.value)}/></label>
 <button className="refresh" disabled={busy||!query.trim()} type="submit">搜索模型</button></form>
 {results.length?<div className="model-results">{results.map((c,i)=><button key={c.model_id+i} className={"model-result"+(selected===c?" chosen":"")} disabled={busy} onClick={()=>choose(c)}><b>{c.model_id}</b><small>许可：{c.license??"未知"} · {c.restricted?"受限":"待核验"}</small></button>)}</div>:<div className="empty">暂无搜索结果</div>}
 {selected&&<div className="model-approval"><h3>下载入队：{selected.model_id}</h3>
 {source==="modelscope"&&<><button className="refresh" disabled={busy} onClick={()=>void execute({kind:"revisions",model_id:selected.model_id},data=>setRevisions(JSON.stringify(data,null,2)??""))}>获取版本信息</button>{revisions&&<pre className="revision-list">{revisions}</pre>}</>}
 <label>完整版本 SHA（40 位）<input value={revision} maxLength={40} disabled={busy} onChange={e=>{setRevision(e.target.value);setReviewed(false)}}/></label>
 <label>已审核许可标识<input value={license} maxLength={100} disabled={busy} onChange={e=>{setLicense(e.target.value);setReviewed(false)}}/></label>
 <label>下载预算上限（GiB）<input type="number" min="1" step="1" value={budget} disabled={busy} onChange={e=>{setBudget(e.target.value);setReviewed(false)}}/></label>
 <label className="review-check"><input type="checkbox" checked={reviewed} disabled={busy} onChange={e=>setReviewed(e.target.checked)}/>我已审核此版本的许可证和预定用途，并确认预算。</label>
 <p className="muted">实际下载前仍由后端校验公开性、许可、文件和预算。入队后点击下方“启动下载队列”，执行器按顺序处理已确认的任务。</p>
 <button className="refresh" disabled={busy||!ready} onClick={()=>void execute({kind:"enqueue",source,model_id:selected.model_id,revision,license,max_bytes:bytes,reviewed:true},async()=>{setReviewed(false);setMessage("已登记下载任务，请核对队列。");await refresh()})}>确认并加入下载队列</button></div>}
 </section>
 <section className="panel"><h2>下载任务控制 <small>最近 50 项 · 自动刷新</small></h2>
 <div className="download-card"><div><b>{worker?.message??"尚未取得执行器状态"}</b><small>待处理 {fmt(queued)} 项 · 活动 {fmt(active)} 项{stale?" · 快照可能过期":""}</small></div><div className="queue-actions"><button className="refresh" disabled={busy||stale||!worker||worker.running||!queued||!!active} onClick={()=>void execute({kind:"worker-start"},async()=>{setMessage("已启动本地执行器，进度以队列为准。");await refresh()})}>启动下载队列</button><button className="refresh" disabled={busy||!worker?.running||worker.stop_requested} onClick={()=>void execute({kind:"worker-stop"},async()=>{setMessage("当前任务结束后停止调度。");await refresh()})}>停止调度</button></div></div>
 {rows.length?rows.map(r=>{const state=String(r.state),id=String(r.id);return <div className="download-card" key={id}><div><b>{r.model_id}</b><small>{labels[state]??state} · 已验证 {fmt(r.done_bytes)} / {fmt(r.total_bytes)} 字节 · 校验处理速率 {fmt(r.rate)} B/s</small><small>{r.source==="modelscope"?"ModelScope（文件级恢复，未提供网络速率）":"Hugging Face（字节级续传）"} · 本次网络接收 {fmt(r.network_bytes)} 字节 · 最近采样网络速率 {fmt(r.network_rate)} B/s · 按校验速率估算剩余 {typeof r.eta==="number"?Math.ceil(r.eta)+" 秒":"—"}</small>{typeof r.total_bytes==="number"&&typeof r.done_bytes==="number"&&r.total_bytes>0&&r.done_bytes>=0&&r.done_bytes<=r.total_bytes&&<progress max={r.total_bytes} value={r.done_bytes}/>}</div><div className="queue-actions">{(["pause","resume","cancel"] as const).map(kind=><button className="refresh" key={kind} disabled={busy||!(kind==="pause"?["queued","running"]:kind==="resume"?["paused","failed","interrupted"]:["queued","paused","failed","interrupted","running","pause_requested"]).includes(state)} onClick={()=>void execute({kind,id},async()=>{setMessage("操作已提交，状态以实际快照为准。");await refresh()})}>{kind==="pause"?"暂停":kind==="resume"?"恢复":"取消"}</button>)}</div></div>}):<div className="empty">暂无下载任务</div>}
 {rows.filter(r=>["running","pause_requested","cancel_requested"].includes(String(r.state))).map(r=><div className="download-card" key={"recover-"+r.id}><div><small>异常恢复：{r.model_id}（仅在确认原下载进程已完全退出时使用）</small><label><input type="checkbox" checked={recoverId===r.id} disabled={busy||stale||!worker||worker.running} onChange={e=>setRecoverId(e.target.checked?String(r.id):null)}/>我已确认所有原执行器进程均已退出</label></div><button className="refresh" disabled={busy||stale||!worker||worker.running||recoverId!==r.id} onClick={()=>{setRecoverId(null);void execute({kind:"recover",id:String(r.id),worker_stopped:true},async()=>{setMessage("已提交异常恢复，请核对实际状态。");await refresh()})}}>恢复异常任务</button></div>)}
 <p className="muted">执行器仅在用户启动后处理已入队任务，成功后处理下一项，失败/暂停/取消后停止本轮。停止调度不会强制终止当前下载。暂停/取消为协作式控制；缓存校验速率和估算剩余时间不等同网络带宽或网络 ETA。异常退出后不得未经确认恢复其他执行器的任务。</p></section>
 {error&&<div role="alert" className="error">{error}</div>}{message&&<div role="status" className="model-message">{message}</div>}
 </>
}
