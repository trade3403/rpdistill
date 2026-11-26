import React,{useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import type {Snapshot,Row} from "./protocol";
import {ModelCenter} from "./model-center";
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
   <article className="panel loss-panel"><div className="panel-heading"><h2>训练 Loss 曲线</h2><small>实时监控</small></div>
   <div className="chart-placeholder" aria-label="暂无训练 Loss 数据"><div className="chart-grid"/><div className="chart-note"><b>暂无训练曲线</b><small>后端尚未提供逐步 Loss 数据</small></div></div></article>
   <article className="panel gpu-panel"><div className="panel-heading"><h2>GPU 监控</h2><small>真实硬件快照</small></div>
   {d?.nvidia?.devices?.length?d.nvidia.devices.map(g=><div className="gpu-card" key={g.index}><b>{g.name}</b><small>显存已用 {g.total_mib-g.free_mib} / {g.total_mib} MiB</small>{g.total_mib>0&&g.free_mib>=0&&g.free_mib<=g.total_mib&&<meter min={0} max={g.total_mib} value={g.total_mib-g.free_mib}/>}<small>GPU 利用率：未接入</small></div>):<div className="empty">尚无 NVIDIA GPU 记录 · {d?.nvidia?.status??"未取得快照"}</div>}
   <div className="monitor-hardware"><span>CPU <b>{value(d?.logical_cpus)} 核</b></span><span>内存 <b>{size(d?.memory_bytes)}</b></span></div></article>
  </section>
  <section className="panel log-panel"><div className="panel-heading"><h2>任务日志</h2><small>最近任务错误摘要</small></div>{errors.length?<Table rows={errors} fields={[["updated","更新时间"],["id","任务 ID"],["error","错误摘要"]]}/>:<div className="log-empty">暂无已读取的任务错误 · 实时事件流尚未接入</div>}</section>
 </>
}
function App(){
 const [data,setData]=useState<Snapshot|null>(null),[error,setError]=useState(""),[tab,setTab]=useState(0),[busy,setBusy]=useState(false);
 async function refresh(){setBusy(true);try{const r=await window.studio.snapshot();if(r.ok){setData(r.data);setError("")}else setError(r.error)}
 catch{setError("无法连接桌面后端")}finally{setBusy(false)}}
 useEffect(()=>{void refresh();const id=setInterval(()=>void refresh(),10000);return()=>clearInterval(id)},[]);
 const c=data?.counts,r=data?.rows,d=data?.devices;
 const counts=[["登记教师模型",c?c.teachers+c.modelscope_teachers:undefined],["科研论文",c?.papers],["已存全文",c?.fulltexts],["语料分段",c?.segments],["双语候选",c?.pairs],["数据集版本",c?.datasets]];
 const smokeStarted=React.useRef(false);
 useEffect(()=>{if(data&&!smokeStarted.current&&typeof (window as any).studioSmoke==="function"){
 smokeStarted.current=true;const ok=data.schema==="rpdistill-studio-snapshot-v1"&&data.read_only===true&&typeof (window as any).require==="undefined"&&document.querySelectorAll(".metric").length===6&&document.querySelector(".config-panel")!==null&&document.querySelector(".loss-panel")!==null&&document.querySelectorAll(".config-actions button:disabled").length===3&&data.counts.downloads===1&&document.body.textContent?.includes("fixture/model")===true;
 const id=String(data.rows.downloads?.[0]?.id);
 void (async()=>{try{
  const invalid=await window.studio.modelAction({kind:"pause",id:"--help"});
  const unapproved=await window.studio.modelAction({kind:"enqueue",source:"huggingface",model_id:"fixture/second",revision:"b".repeat(40),license:"apache-2.0",max_bytes:1024,reviewed:false});
  const paused=await window.studio.modelAction({kind:"pause",id});
  const p=await window.studio.snapshot();
  const resumed=await window.studio.modelAction({kind:"resume",id});
  const enqueued=await window.studio.modelAction({kind:"enqueue",source:"huggingface",model_id:"fixture/second",revision:"b".repeat(40),license:"apache-2.0",max_bytes:1024,reviewed:true});
  const q=await window.studio.snapshot();
  (window as any).studioSmoke(ok&&!invalid.ok&&!unapproved.ok&&paused.ok&&p.ok&&p.data.rows.downloads[0]?.state==="paused"&&resumed.ok&&enqueued.ok&&q.ok&&q.data.counts.downloads===2&&q.data.rows.downloads.every(r=>r.state==="queued"));
 }catch{(window as any).studioSmoke(false)}})();
 }},[data]);
 return <div className={tab===0?"shell dashboard-shell":"shell"}><aside><div className="brand"><span className="logo">RP</span><div>RPDistill<span>STUDIO · 知识蒸馏</span></div></div>
 <div className="navlabel">工作空间</div>{tabs.map((t,i)=><button className={tab===i?"nav active":"nav"} onClick={()=>setTab(i)} key={t}><span>{["◈","▣","▤","◉","◇"][i]}</span>{t}</button>)}
 <div className="aside-bottom">本地工作空间<br/><small>本地工作台 · E11b1</small></div></aside>
 <main><header><div><div className="eyebrow">RPTRANSLATE / 自主模型训练</div><h1>{tabs[tab]}</h1></div><div className="header-actions"><span className={error?"status bad":"status"}>{error?"连接异常":data?"本地后端已连接":"正在连接"}</span><button className="refresh" onClick={()=>void refresh()} disabled={busy}>{busy?"刷新中…":"刷新状态"}</button></div></header>
 {error&&<div role="alert" className="error">{error}；现有数据显示为上次成功快照。</div>}
 <div className="subline">本地真实记录 · {data?.observed_at?new Date(data.observed_at).toLocaleString():"尚未取得快照"}{data&&!data.database_exists?" · 尚无任务数据库":""}</div>
 {tab===0&&<><section className="hero"><div><div className="eyebrow">AUTOMATED DISTILLATION</div><h2>全自动蒸馏控制中心</h2><p>采集、语料、训练与模型验收的统一状态视图</p></div><span className="tag">监控模式</span></section>
 <section className="metrics">{counts.map(([label,n])=><article className="metric" key={String(label)}><span>{label}</span><strong>{value(n)}</strong><small>本地数据库记录</small></article>)}</section>
 <section className="panel"><h2>自动化阶段流水线</h2><div className="pipeline">{stages.map((s,i)=><div key={s}><b>{String(i+1).padStart(2,"0")}</b><span>{s}</span></div>)}</div><p className="muted">流程示意，不表示当前任务已完成；任务状态见下方。</p></section><MonitorPanels data={data}/></>}
 {(tab===0||tab===3)&&<section className="panel"><h2>训练任务 <small>{value(c?.training)} 项</small></h2><Table rows={r?.training??[]} fields={[["id","任务 ID"],["state","状态"],["step","优化器步数"],["attempt","执行次数"],["updated","更新时间"]]}/><p className="muted">实时 loss、GPU 利用率曲线尚未接入，不显示模拟数据。</p></section>}
 {tab===1&&<ModelCenter rows={r?.downloads??[]} refresh={refresh}/>}
 {tab===0&&<section className="panel"><h2>模型下载 <small>{value(c?.downloads)} 项</small></h2><Table rows={r?.downloads??[]} fields={[["model_id","模型"],["state","状态"],["done_bytes","已完成字节"],["total_bytes","总字节"],["rate","记录速率"],["eta","预计剩余秒"]]}/></section>}
 {tab===1&&<section className="panel"><h2>已登记教师模型</h2><h3>Hugging Face</h3><Table rows={r?.teachers??[]} fields={[["model_id","模型"],["revision","固定版本"],["license","许可"]]}/><h3>ModelScope</h3><Table rows={r?.modelscope_teachers??[]} fields={[["model_id","模型"],["revision","固定版本"],["license","许可"]]}/></section>}
 {tab===2&&<><section className="metrics">{counts.slice(1).map(([label,n])=><article className="metric" key={String(label)}><span>{label}</span><strong>{value(n)}</strong></article>)}</section><section className="panel"><h2>语料流水线任务</h2><Table rows={r?.pipelines??[]} fields={[["id","任务 ID"],["state","状态"],["stage","阶段"],["updated","更新时间"]]}/></section></>}
 {tab===4&&<section className="panel"><h2>评测与导出</h2><p>后端评测与候选模型导出功能已存在，图形化操作尚未接入。</p><div className="empty">暂无已加载的评测报告 · 不代表质量通过</div></section>}
 <section className="panel hardware"><h2>本地硬件</h2><div className="hardware-grid"><div><span>处理器</span><strong>{value(d?.logical_cpus)} 逻辑核心</strong><small>{d?.platform} {d?.architecture}</small></div><div><span>系统内存</span><strong>{size(d?.memory_bytes)}</strong></div><div><span>磁盘可用</span><strong>{size(d?.disk?.free_bytes)}</strong></div><div><span>NVIDIA GPU</span><strong>{d?.nvidia?.devices?.length??"—"} 张</strong><small>{d?.nvidia?.status??"未检测"}</small></div></div>{d?.nvidia?.devices?.map(g=><div className="gpu" key={g.index}>{g.name} · {g.free_mib} / {g.total_mib} MiB 空闲</div>)}<p className="muted">硬件识别不代表 CUDA 训练就绪。</p></section>
 <footer>RPDistill Studio {data?.version??""} · 模型队列控制 · 训练及自动化控制待接入</footer>
 </main>{tab===0&&<TaskConfig data={data}/>}</div>
}
createRoot(document.getElementById("root")!).render(<App/>);
