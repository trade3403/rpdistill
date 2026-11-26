export const SCHEMA = "rpdistill-studio-snapshot-v1";
export interface Row { [key:string]: string | number | null }
export interface Snapshot {
  schema: typeof SCHEMA; version:string; observed_at:string; database_exists:boolean;
  counts:Record<string,number>; rows:Record<string,Row[]>;
  devices:{platform:string;architecture:string;logical_cpus:number|null;memory_bytes:number|null;
    disk:{free_bytes:number;total_bytes:number};nvidia:{status:string;devices:{index:number;name:string;total_mib:number;free_mib:number}[]}};
  read_only:true;training_metrics_available:false;release_ready:false;
}
export type Reply = {ok:true;data:Snapshot}|{ok:false;error:string};
export type ModelSource="huggingface"|"modelscope";
export type ModelRequest =
 | {kind:"search";source:ModelSource;query:string}
 | {kind:"revisions";model_id:string}
 | {kind:"enqueue";source:ModelSource;model_id:string;revision:string;license:string;max_bytes:number;reviewed:boolean}
 | {kind:"pause"|"resume"|"cancel";id:string};
export type ModelReply={ok:true;data:unknown}|{ok:false;error:string};
export interface StudioAPI {snapshot:()=>Promise<Reply>;modelAction:(request:ModelRequest)=>Promise<ModelReply>}
declare global {interface Window {studio:StudioAPI}}
