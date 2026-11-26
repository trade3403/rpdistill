export const SCHEMA = "rpdistill-studio-snapshot-v1";
export interface Row { [key:string]: string | number | null }
export interface WorkerStatus {running:boolean;stop_requested:boolean;message:string}
export interface Snapshot {
  checkpoint_min_bytes?:number;
  student_resources?:{state:"missing"|"invalid"|"verified";source:string;revision:string;file_count:number;asset_bytes:number;assets_free_bytes:number|null;checkpoint_free_bytes:number|null;dependencies:Record<string,boolean>;runtime_verified:false};
  local_asset_worker?:WorkerStatus;
  local_environment_worker?:WorkerStatus;
  environment?:{deploy_available:boolean;source:"external"|"managed"|"base";profile:"cpu"|"cu128"|null;torch:string|null;cuda_available:boolean|null};
  local_evaluation_worker?:WorkerStatus;
  local_worker?:WorkerStatus;
  local_training_worker?:WorkerStatus;
  local_corpus_worker?:{running:boolean;id:string|null;message:string};
  schema: typeof SCHEMA; version:string; observed_at:string; database_exists:boolean;
  counts:Record<string,number>; rows:Record<string,Row[]>;
  devices:{platform:string;architecture:string;logical_cpus:number|null;memory_bytes:number|null;
    disk:{free_bytes:number;total_bytes:number};nvidia:{status:string;devices:{index:number;name:string;total_mib:number;free_mib:number;utilization_percent?:number|null;temperature_c?:number|null;power_w?:number|null}[]}};
  read_only:true;training_metrics_available:boolean;release_ready:false;
}
export type Reply = {ok:true;data:Snapshot}|{ok:false;error:string};
export type ModelSource="huggingface"|"modelscope";
export type ModelRequest =
 | {kind:"search";source:ModelSource;query:string}
 | {kind:"revisions";model_id:string}
 | {kind:"enqueue";source:ModelSource;model_id:string;revision:string;license:string;max_bytes:number;reviewed:boolean}
 | {kind:"pause"|"resume"|"cancel";id:string}
 | {kind:"worker-start"|"worker-stop"}
 | {kind:"recover";id:string;worker_stopped:boolean}
 | {kind:"pipeline-create";source:ModelSource;model_id:string;revision:string;keyword:string;start_date:string;end_date:string;device:string;dtype:string;search_limit:number;paper_limit:number;segment_limit:number;max_bytes:number;approved:boolean}
 | {kind:"pipeline-run";id:string;approved:boolean}
 | {kind:"pipeline-resume";id:string;worker_stopped:boolean}
 | {kind:"training-enqueue";version:string;license:string;steps:number;batch_size:number;learning_rate:number;accumulation:number;device:string;precision:string;cuda_bytes:number;segment_steps:number;segment_seconds:number;total_seconds:number;checkpoint_bytes:number;total_checkpoint_bytes:number;approved:boolean}
 | {kind:"environment-deploy";profile:"cpu"|"cu128";approved:boolean}
 | {kind:"student-assets";approved:boolean}
 | {kind:"review-run";id:string;mode:"rust"|"blind"|"collect";timeout_seconds:number;approved:boolean}
 | {kind:"integration-run";id:string;artifact_id:string;reviewed_dataset:string;reviewed_teacher_license:string;reviewed_model_license:string;rights_note:string;reviewer:string;max_seconds:number;training_limit:number;approved:boolean}
 | {kind:"receipt-check";id:string;approved:boolean}
 | {kind:"review-recover";id:string;worker_stopped:boolean}
 | {kind:"artifact-run";id:string;mode:"fp32"|"fp16"|"int8"|"export";max_bytes:number;max_seconds:number;license_label:string;rights_note:string;approved:boolean}
 | {kind:"artifact-recover";id:string;worker_stopped:boolean}
 | {kind:"evaluate-job";id:string;review_note:string;approved:boolean}
 | {kind:"evaluation-recover";id:string;worker_stopped:boolean}
 | {kind:"training-start";approved:boolean}
 | {kind:"training-pause"|"training-resume"|"training-cancel";id:string}
 | {kind:"training-recover";id:string;worker_stopped:boolean};
export type ModelReply={ok:true;data:unknown}|{ok:false;error:string};
export interface StudioAPI {snapshot:()=>Promise<Reply>;modelAction:(request:ModelRequest)=>Promise<ModelReply>}
declare global {interface Window {studio:StudioAPI}}
