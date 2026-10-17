import {defineConfig} from 'vite';
import {readFileSync} from 'node:fs';

// `npm run build` keeps the served dist/ (release_server, Sites). `npm run build:office` makes one self-contained
// HTML for file:// next to the agent-office records: no server, so images used as WebGL textures must be inlined
// (a file:// image taints the canvas) and every dynamic import is folded into the single script.
const ASSETS='virtual:factory-assets',CHARACTERS=['researcher-team-v1','researcher-work-v1','researcher-walk-v2'];
const WORKER='pdfjs-dist/build/pdf.worker.min.mjs?url';
function factoryAssets(office){
  return {name:'factory-assets',enforce:'pre',
    resolveId(id){if(id===ASSETS)return '\0'+ASSETS;if(office&&id===WORKER)return '\0office-pdf-worker';},
    load(id){
      if(id==='\0office-pdf-worker')return "import code from 'pdfjs-dist/build/pdf.worker.min.mjs?raw';export default URL.createObjectURL(new Blob([code],{type:'text/javascript'}));";
      if(id!=='\0'+ASSETS)return;
      const characters=CHARACTERS.map(name=>office?'data:image/png;base64,'+readFileSync(new URL(`./public/characters/${name}.png`,import.meta.url)).toString('base64'):`/characters/${name}.png`);
      // The recorded motion video is not inlined into the file page; the live recorder still works there.
      return `export const characters=${JSON.stringify(characters)};export const motionVideo=${office?'null':JSON.stringify('/media/researcher-motion-demo-v4.mp4')};`;
    }};
}
export default defineConfig(({mode})=>mode==='office'?{
  base:'./',publicDir:false,plugins:[factoryAssets(true)],
  build:{outDir:'dist-office',emptyOutDir:true,cssCodeSplit:false,assetsInlineLimit:100_000_000,modulePreload:false,chunkSizeWarningLimit:16000,
    rollupOptions:{output:{inlineDynamicImports:true}}},
}:{plugins:[factoryAssets(false)]});
