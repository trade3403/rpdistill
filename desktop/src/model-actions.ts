// Only a fixed, bounded CLI protocol is exposed to the renderer.
const validId=(v:unknown):v is string=>typeof v==="string"&&/^[A-Za-z0-9_][A-Za-z0-9_.-]{0,95}(\/[A-Za-z0-9_][A-Za-z0-9_.-]{0,95})?$/.test(v)&&!v.includes("..")&&!v.includes("--")&&!/[.-]$|\.git$/.test(v);
const validSource=(v:unknown):v is "huggingface"|"modelscope"=>v==="huggingface"||v==="modelscope";
export function modelArgs(value:unknown):string[]{
 if(!value||typeof value!=="object"||Array.isArray(value))throw Error("request");
 const r=value as Record<string,unknown>;
 const exact=(keys:string[])=>{if(Object.keys(r).length!==keys.length||Object.keys(r).some(k=>!keys.includes(k)))throw Error("fields")};
 const integer=(v:unknown,lo:number,hi:number):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>=lo&&v<=hi;
 const date=(v:unknown):v is string=>typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v);
 const job=(v:unknown):v is string=>typeof v==="string"&&/^[a-f0-9]{32}$/.test(v);
 switch(r.kind){
 case "pipeline-create":
  exact(["kind","source","model_id","revision","keyword","start_date","end_date","device","dtype","search_limit","paper_limit","segment_limit","max_bytes","approved"]);
  if(!validSource(r.source)||!validId(r.model_id)||(r.source==="modelscope"&&!r.model_id.includes("/"))||
    typeof r.revision!=="string"||!/^[a-f0-9]{40}$/.test(r.revision)||
    typeof r.keyword!=="string"||!r.keyword.trim()||r.keyword.length>200||/[\x00-\x1f\x7f"\\]/.test(r.keyword)||
    !date(r.start_date)||!date(r.end_date)||r.start_date>r.end_date||
    typeof r.device!=="string"||!/^cpu$|^cuda:[0-9]{1,3}$/.test(r.device)||
    typeof r.dtype!=="string"||!["float32","float16","bfloat16"].includes(r.dtype)||(r.device==="cpu"&&r.dtype!=="float32")||
    !integer(r.search_limit,1,500)||!integer(r.paper_limit,1,50)||!integer(r.segment_limit,1,1024)||
    !integer(r.max_bytes,1,2**40)||r.approved!==true)throw Error("pipeline configuration");
  return ["pipeline-create",r.model_id,"--revision",r.revision,"--source",r.source,
   "--keyword="+r.keyword.trim(),"--start-date",r.start_date,"--end-date",r.end_date,
   "--device",r.device,"--dtype",r.dtype,"--search-limit",String(r.search_limit),
   "--paper-limit",String(r.paper_limit),"--segment-limit",String(r.segment_limit),"--max-bytes",String(r.max_bytes)];
 case "pipeline-run":
  exact(["kind","id","approved"]);
  if(!job(r.id)||r.approved!==true)throw Error("pipeline start");
  return ["pipeline-run",r.id];
 case "pipeline-resume":
  exact(["kind","id","worker_stopped"]);
  if(!job(r.id)||r.worker_stopped!==true)throw Error("pipeline recovery");
  return ["pipeline-resume",r.id,"--worker-stopped"];
 case "search":
  exact(["kind","source","query"]);
  if(!validSource(r.source)||typeof r.query!=="string"||!r.query.trim()||r.query.length>100||/[\x00-\x1f\x7f]/.test(r.query))throw Error("search");
  return ["model-search","--source",r.source,"--limit","20","--",r.query.trim()];
 case "revisions":
  exact(["kind","model_id"]);
  if(!validId(r.model_id)||!r.model_id.includes("/"))throw Error("id");
  return ["model-revisions",r.model_id];
 case "enqueue":
  exact(["kind","source","model_id","revision","license","max_bytes","reviewed"]);
  if(!validSource(r.source)||!validId(r.model_id)||(r.source==="modelscope"&&!r.model_id.includes("/"))||
   typeof r.revision!=="string"||!/^[a-f0-9]{40}$/.test(r.revision)||
   typeof r.license!=="string"||!/^[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}$/.test(r.license)||
   typeof r.max_bytes!=="number"||!Number.isSafeInteger(r.max_bytes)||r.max_bytes<=0||r.reviewed!==true)throw Error("approval");
  return ["download-enqueue",r.model_id,"--source",r.source,"--revision",r.revision,"--reviewed-license",r.license,"--max-bytes",String(r.max_bytes)];
 case "worker-start":case "worker-stop":
  exact(["kind"]);
  return [r.kind];
 case "recover":
  exact(["kind","id","worker_stopped"]);
  if(typeof r.id!=="string"||!/^[a-f0-9]{32}$/.test(r.id)||r.worker_stopped!==true)throw Error("recovery");
  return ["download-recover",r.id,"--worker-stopped"];
 case "pause":case "resume":case "cancel":
  exact(["kind","id"]);
  if(typeof r.id!=="string"||!/^[a-f0-9]{32}$/.test(r.id))throw Error("job");
  return ["download-"+r.kind,r.id];
 default:throw Error("command");
 }
}
