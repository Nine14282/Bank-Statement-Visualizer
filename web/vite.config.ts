import fs from 'node:fs'
import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { viteSingleFile } from 'vite-plugin-singlefile'
import { defineConfig, type Plugin } from 'vite'

// Must match index.html and workspace/build_dashboard.py (MARK) byte for byte.
const MARK = '<script id="ledger-data" type="application/json">null</script>'

// Dev server only: put the ledger the Python build last wrote (src/data/ledger.json, git-ignored) into the page, the
// way build_dashboard.py does for the real dashboard. `apply: 'serve'` keeps it out of `vite build`, so the committed
// prebuilt page never contains anyone's data. `<` is escaped so no description can close the script tag.
const devLedger: Plugin = {
  name: 'dev-ledger-data',
  apply: 'serve',
  transformIndexHtml(html) {
    const file = path.resolve(import.meta.dirname, 'src/data/ledger.json')
    if (!fs.existsSync(file)) return html
    const json = fs.readFileSync(file, 'utf8').replace(/</g, '\\u003c')
    return html.replace(MARK, () => `<script id="ledger-data" type="application/json">${json}</script>`)
  },
}

// singlefile: one self-contained page with no data, committed as prebuilt/index.html. Users' builds are Python only
// (workspace/build_dashboard.py fills in the data), so they need no Node.
export default defineConfig({
  plugins: [react(), tailwindcss(), viteSingleFile(), devLedger],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  publicDir: false,
  build: { outDir: 'prebuilt' },
})
