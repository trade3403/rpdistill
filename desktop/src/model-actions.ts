// Only a fixed, bounded CLI protocol is exposed to the renderer.
const validId=(v:unknown):v is string=>typeof v==="string"&&/^[A-Za-z0-9_][A-Za-z0-9_.-]{0,95}(\/[A-Za-z0-9_][A-Za-z0-9_.-]{0,95})?$/.test(v)&&!v.includes("..")&&!v.includes("--")&&!/[.-]$|\.git$/.test(v);
const validSource=(v:unknown):v is "huggingface"|"modelscope"=>v==="huggingface"||v==="modelscope";
export function modelArgs(value:unknown):string[]{
 if(!value||typeof value!=="object"||Array.isArray(value))throw Error("request");
 const r=value as Record<string,unknown>;
 const exact=(keys:string[])=>{if(Object.keys(r).length!==keys.length||Object.keys(r).some(k=>!keys.includes(k)))throw Error("fields")};
 switch(r.kind){
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
 case "pause":case "resume":case "cancel":
  exact(["kind","id"]);
  if(typeof r.id!=="string"||!/^[a-f0-9]{32}$/.test(r.id))throw Error("job");
  return ["download-"+r.kind,r.id];
 default:throw Error("command");
 }
}
