import {contextBridge,ipcRenderer} from "electron";
import type {StudioAPI} from "./protocol";
const api:StudioAPI={snapshot:()=>ipcRenderer.invoke("studio:snapshot")};
contextBridge.exposeInMainWorld("studio",Object.freeze(api));
// Test-only channel is unavailable unless main explicitly enables it.
if(process.argv.includes("--studio-smoke")) contextBridge.exposeInMainWorld("studioSmoke",(ok:boolean)=>ipcRenderer.invoke("studio:smoke-result",ok));
