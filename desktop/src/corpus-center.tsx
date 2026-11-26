import React,{useState} from "react";
import type {ModelRequest,ModelSource,Snapshot} from "./protocol";
const states:Record<string,string>={queued:"待启动",running:"运行中",failed:"失败",interrupted:"中断",candidate_complete:"候选数据集已生成",insufficient_candidates:"候选数量不足"};
const stages=["论文检索","合法全文下载","语料解析","教师翻译","候选数据集","周期结束"];
const show=(v:unknown)=>v===null||v===undefined?"—":String(v);
export function CorpusCenter({data,refresh,stale}:{data:Snapshot|null;refresh:()=>Promise<void>;stale:boolean}){
 const teachers=(["huggingface","modelscope"] as const).flatMap(source=>(data?.rows[source==="huggingface"?"teachers":"modelscope_teachers"]??[]).map(row=>({source,model_id:String(row.model_id),revision:String(row.revision),license:row.license})));
 const key=(t:{source:ModelSource;model_id:string;revision:string})=>t.source+":"+t.model_id+":"+t.revision;
 const [teacherKey,setTeacher]=useState(""),[keyword,setKeyword]=useState(""),[start,setStart]=useState(""),[end,setEnd]=useState("");
 const [device,setDevice]=useState("cpu"),[dtype,setDtype]=useState("float32"),[searchLimit,setSearchLimit]=useState("100"),[paperLimit,setPaperLimit]=useState("20"),[segments,setSegments]=useState("1000"),[budget,setBudget]=useState(""),[approved,setApproved]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState(""),[runId,setRunId]=useState<string|null>(null),[recoverId,setRecoverId]=useState<string|null>(null);
 const teacher=teachers.find(t=>key(t)===teacherKey),worker=data?.local_corpus_worker;
 const active=!!worker?.running||!!data?.local_worker?.running||!!data?.counts.pipeline_active||!!data?.counts.download_active;
 const locked=busy||stale||!data;
 function changed(){setApproved(false)}
 async function send(request:ModelRequest,success:string){
  setBusy(true);setError("");setMessage("");
  try{const reply=await window.studio.modelAction(request);if(reply.ok){setMessage(success);await refresh()}else setError(reply.error)}
  catch{setError("语料操作连接失败，请刷新实际任务状态")}finally{setBusy(false)}
 }
 const bytes=Number(budget)*1024**2;
 const int=(s:string,min:number,max:number)=>Number.isSafeInteger(Number(s))&&Number(s)>=min&&Number(s)<=max;
 const ready=!!teacher&&!!teacher.license&&keyword.trim().length>0&&!!start&&!!end&&start<=end&&int(searchLimit,1,500)&&int(paperLimit,1,50)&&int(segments,1,1024)&&Number.isSafeInteger(bytes)&&bytes>0&&bytes<=2**40&&approved;
 return <>
 <section className="panel corpus-center"><div className="panel-heading"><h2>创建单次科研语料流水线</h2><small>NCBI PMC · 英译中</small></div>
 <p className="muted">仅开放获取论文；许可不符或未知的全文由后端拒绝。使用共享论文目录和已登记教师，候选语料需人工复核后才可训练。此页不支持持续模式或远程 API。</p>
 <div className="corpus-form" onChange={changed}>
 <label className="wide">已登记教师<select disabled={locked} value={teacherKey} onChange={e=>setTeacher(e.target.value)}><option value="">请选择教师模型</option>{teachers.map(t=><option key={key(t)} value={key(t)}>{t.model_id} · {t.source} · {t.revision.slice(0,12)}</option>)}</select></label>
 {teacher&&<p className="wide muted">固定版本：{teacher.revision} · 登记许可：{show(teacher.license)}</p>}
 <label className="wide">检索关键词<input disabled={locked} maxLength={200} value={keyword} onChange={e=>setKeyword(e.target.value)} placeholder="英文科研主题"/></label>
 <label>发表起始日期<input disabled={locked} type="date" value={start} onChange={e=>setStart(e.target.value)}/></label>
 <label>发表截止日期<input disabled={locked} type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label>
 <label>检索记录上限<input type="number" min="1" max="500" disabled={locked} value={searchLimit} onChange={e=>setSearchLimit(e.target.value)}/></label>
 <label>全文篇数上限<input type="number" min="1" max="50" disabled={locked} value={paperLimit} onChange={e=>setPaperLimit(e.target.value)}/></label>
 <label>翻译分段上限<input type="number" min="1" max="1024" disabled={locked} value={segments} onChange={e=>setSegments(e.target.value)}/></label>
 <label>全文下载预算（MiB）<input type="number" min="1" max="1048576" disabled={locked} value={budget} onChange={e=>setBudget(e.target.value)}/></label>
 <label>推理设备<select disabled={locked} value={device} onChange={e=>{setDevice(e.target.value);setDtype("float32")}}><option value="cpu">CPU</option>{(data?.devices.nvidia?.devices??[]).map(g=><option key={g.index} value={"cuda:"+g.index}>{g.name} (CUDA {g.index})</option>)}</select></label>
 <label>精度<select disabled={locked||device==="cpu"} value={dtype} onChange={e=>setDtype(e.target.value)}><option value="float32">FP32</option><option value="float16">FP16</option><option value="bfloat16">BF16</option></select></label>
 </div>
 <label className="review-check"><input type="checkbox" checked={approved} disabled={locked} onChange={e=>setApproved(e.target.checked)}/>已审查教师许可和用途，确认论文下载预算与单次运行配置；GPU 识别不保证 CUDA 可用。</label>
 <p className="muted">默认候选门槛：训练 10、验证 1、测试 1；不自动启动训练。创建任务不会联网，下一步须单独确认启动。</p>
 <button className="refresh" disabled={locked||!ready} onClick={()=>{if(!teacher)return;setApproved(false);void send({kind:"pipeline-create",source:teacher.source,model_id:teacher.model_id,revision:teacher.revision,keyword,start_date:start,end_date:end,device,dtype,search_limit:Number(searchLimit),paper_limit:Number(paperLimit),segment_limit:Number(segments),max_bytes:bytes,approved:true},"已创建持久任务，请确认启动。")}}>创建语料任务</button>
 </section>
 <section className="panel"><h2>语料任务 <small>{worker?.message??"尚未取得执行器状态"}</small></h2>
 {(data?.rows.pipelines??[]).map(row=>{const id=String(row.id),state=String(row.state),stage=Number(row.stage);return <div className="corpus-job" key={id}>
 <div><b>{show(row.keyword)} · {show(row.model_id)}</b><small>{id} · {states[state]??state} · {stages[stage]??"未知阶段"}</small><small>已提交阶段 {stage}/5 · 全文预算 {show(row.max_bytes)} 字节 · 篇数上限 {show(row.paper_limit)}{row.error?" · "+row.error:""}</small>{row.dataset_version&&<small>候选版本：{row.dataset_version}</small>}</div>
 {state==="queued"&&<><label className="review-check"><input type="checkbox" disabled={locked||active} checked={runId===id} onChange={e=>setRunId(e.target.checked?id:null)}/>确认按保存的配置联网采集及翻译</label><button className="refresh" disabled={locked||active||runId!==id} onClick={()=>{setRunId(null);void send({kind:"pipeline-run",id,approved:true},"已启动语料执行器，实际状态以数据库为准。")}}>启动单次流水线</button></>}
 {["failed","interrupted","running"].includes(state)&&stage>=2&&<><label className="review-check"><input type="checkbox" disabled={locked||!!worker?.running||!!data?.local_worker?.running} checked={recoverId===id} onChange={e=>setRecoverId(e.target.checked?id:null)}/>确认原语料进程已完全退出</label><button className="refresh" disabled={locked||!!worker?.running||!!data?.local_worker?.running||recoverId!==id} onClick={()=>{setRecoverId(null);void send({kind:"pipeline-resume",id,worker_stopped:true},"已请求恢复，核对排队状态后再启动。")}}>恢复解析/翻译阶段</button></>}
 {["failed","interrupted","running"].includes(state)&&stage<2&&<small>采集中断不可自动重放；须确认原进程退出并重新授权采集预算。</small>}
 </div>})}
 {!data?.rows.pipelines?.length&&<div className="empty">暂无语料任务</div>}
 <p className="muted">当前后端单次语料流水线尚无协作式暂停或取消接口，运行期间禁止正常关闭软件；不强制杀进程，不自动重放采集。</p></section>
 {error&&<div role="alert" className="error">{error}</div>}{message&&<div role="status" className="model-message">{message}</div>}
 </>
}
