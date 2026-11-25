import {build} from "esbuild";
import {mkdir,copyFile} from "node:fs/promises";
await mkdir("dist",{recursive:true});
await build({entryPoints:["src/main.ts","src/preload.ts"],outdir:"dist",outExtension:{".js":".cjs"},platform:"node",format:"cjs",bundle:true,external:["electron"],target:"node22"});
await build({entryPoints:["src/renderer.tsx"],outfile:"dist/renderer.js",bundle:true,platform:"browser",format:"iife",target:"chrome132",minify:true});
await Promise.all(["index.html","style.css"].map(name=>copyFile("src/"+name,"dist/"+name)));
