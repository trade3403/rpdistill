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
 case "environment-deploy":
  exact(["kind","profile","approved"]);
  if((r.profile!=="cpu"&&r.profile!=="cu128")||r.approved!==true)throw Error("environment approval");
  return ["environment-deploy",r.profile];
 case "integration-run":
  exact(["kind","id","artifact_id","reviewed_dataset","reviewed_teacher_license","reviewed_model_license","rights_note","reviewer","max_seconds","training_limit","approved"]);
  const plain=(v:unknown,max:number):v is string=>typeof v==="string"&&!!v.trim()&&v.length<=max&&!/[\x00-\x1f\x7f]/.test(v);
  if(!job(r.id)||!job(r.artifact_id)||typeof r.reviewed_dataset!=="string"||!/^[a-f0-9]{64}$/.test(r.reviewed_dataset)||!plain(r.reviewed_teacher_license,128)||!plain(r.reviewed_model_license,128)||!plain(r.rights_note,2000)||!plain(r.reviewer,128)||!integer(r.max_seconds,1,86400)||!integer(r.training_limit,1,10000)||r.approved!==true)throw Error("integration approval");
  return ["studio-review",r.id,"--kind","integration","--artifact-id",r.artifact_id,"--reviewed-dataset",r.reviewed_dataset,"--reviewed-teacher-license="+r.reviewed_teacher_license,"--reviewed-model-license="+r.reviewed_model_license,"--rights-note="+r.rights_note,"--reviewer="+r.reviewer,"--max-seconds",String(r.max_seconds),"--training-limit",String(r.training_limit),"--approved"];
 case "receipt-check":
  exact(["kind","id","approved"]);
  if(!job(r.id)||r.approved!==true)throw Error("receipt approval");
  return ["studio-review",r.id,"--kind","receipt-check","--approved"];
 case "review-run":
  exact(["kind","id","mode","timeout_seconds","approved"]);
  if(!job(r.id)||typeof r.mode!=="string"||!["rust","blind","collect"].includes(r.mode)||!integer(r.timeout_seconds,1,900)||r.approved!==true)throw Error("review approval");
  return ["studio-review",r.id,"--kind",r.mode,"--timeout-seconds",String(r.timeout_seconds),"--approved"];
 case "review-recover":
  exact(["kind","id","worker_stopped"]);
  if(!job(r.id)||r.worker_stopped!==true)throw Error("review recovery");
  return ["studio-review-recover",r.id,"--worker-stopped"];
 case "artifact-run":
  exact(["kind","id","mode","max_bytes","max_seconds","license_label","rights_note","approved"]);
  if(!job(r.id)||typeof r.mode!=="string"||!["fp32","fp16","int8","export"].includes(r.mode)||!integer(r.max_bytes,1,2**40)||!integer(r.max_seconds,1,86400)||typeof r.license_label!=="string"||r.license_label.length>128||typeof r.rights_note!=="string"||r.rights_note.length>2000||/[\x00-\x1f\x7f]/.test(r.license_label+r.rights_note)||(r.mode==="export"&&(!r.license_label.trim()||!r.rights_note.trim()))||r.approved!==true)throw Error("artifact approval");
  return ["studio-artifact",r.id,"--mode",r.mode,"--max-bytes",String(r.max_bytes),"--max-seconds",String(r.max_seconds),"--license-label="+r.license_label,"--rights-note="+r.rights_note,"--approved"];
 case "artifact-recover":
  exact(["kind","id","worker_stopped"]);
  if(!job(r.id)||r.worker_stopped!==true)throw Error("artifact recovery");
  return ["studio-artifact-recover",r.id,"--worker-stopped"];
 case "evaluate-job":
  exact(["kind","id","review_note","approved"]);
  if(!job(r.id)||typeof r.review_note!=="string"||!r.review_note.trim()||r.review_note.length>2000||/[\x00-\x1f\x7f]/.test(r.review_note)||r.approved!==true)throw Error("evaluation approval");
  return ["studio-evaluate",r.id,"--review-note="+r.review_note.trim(),"--approved"];
 case "evaluation-recover":
  exact(["kind","id","worker_stopped"]);
  if(!job(r.id)||r.worker_stopped!==true)throw Error("evaluation recovery");
  return ["studio-evaluation-recover",r.id,"--worker-stopped"];
 case "student-assets":
  exact(["kind","approved"]);
  if(r.approved!==true)throw Error("asset approval");
  return ["student-assets"];
 case "training-enqueue":
  exact(["kind","version","license","steps","batch_size","learning_rate","accumulation","device","precision","cuda_bytes","segment_steps","segment_seconds","total_seconds","checkpoint_bytes","total_checkpoint_bytes","approved"]);
  if(typeof r.version!=="string"||!/^[a-f0-9]{64}$/.test(r.version)||
   typeof r.license!=="string"||!/^[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}$/.test(r.license)||
   !integer(r.steps,1,10000)||!integer(r.batch_size,1,64)||!integer(r.accumulation,1,64)||
   typeof r.learning_rate!=="number"||!Number.isFinite(r.learning_rate)||r.learning_rate<1e-8||r.learning_rate>0.1||
   typeof r.device!=="string"||!/^(cpu|cuda:[0-9]{1,3})$/.test(r.device)||
   typeof r.precision!=="string"||!["float32","float16","bfloat16"].includes(r.precision)||
   !integer(r.cuda_bytes,0,2**40)||(r.device==="cpu"?(r.cuda_bytes!==0||r.precision!=="float32"):r.cuda_bytes===0)||
   !integer(r.segment_steps,1,10000)||!integer(r.segment_seconds,1,86400)||
   !integer(r.total_seconds,r.segment_seconds,31536000)||!integer(r.checkpoint_bytes,1,2**40)||
   !integer(r.total_checkpoint_bytes,r.checkpoint_bytes,2**44)||r.approved!==true)throw Error("training configuration");
  return ["training-enqueue",r.version,"--reviewed-dataset",r.version,"--reviewed-teacher-license",r.license,
   "--steps",String(r.steps),"--batch-size",String(r.batch_size),"--learning-rate",String(r.learning_rate),
   "--accumulation",String(r.accumulation),"--device",r.device,"--precision",r.precision,
   "--cuda-budget-bytes",String(r.cuda_bytes),"--segment-steps",String(r.segment_steps),"--segment-seconds",String(r.segment_seconds),
   "--total-seconds",String(r.total_seconds),"--max-checkpoint-bytes",String(r.checkpoint_bytes),"--total-checkpoint-bytes",String(r.total_checkpoint_bytes)];
 case "training-start":
  exact(["kind","approved"]);
  if(r.approved!==true)throw Error("training start");
  return ["training-run"];
 case "training-pause":case "training-resume":case "training-cancel":
  exact(["kind","id"]);
  if(!job(r.id))throw Error("training job");
  return [r.kind,r.id];
 case "training-recover":
  exact(["kind","id","worker_stopped"]);
  if(!job(r.id)||r.worker_stopped!==true)throw Error("training recovery");
  return ["training-recover",r.id,"--worker-stopped"];
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
