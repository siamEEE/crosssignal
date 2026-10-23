// Local-only UI checks. Playlist fixtures are synthetic test data, never Qloo answers.
import { writeFile, readFile, mkdir } from 'node:fs/promises'
import { composite, contrast, measureDocument } from './contrast-metrics.mjs'
const output = new URL('../../.review/v31/', import.meta.url)
await mkdir(output, { recursive: true })
const targets = await (await fetch('http://127.0.0.1:9336/json')).json()
const ws = new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl)
await new Promise(r=>ws.addEventListener('open',r,{once:true}))
let id = 0
const waiting = new Map()
const errors = []
ws.addEventListener('message', event => {
  const message = JSON.parse(event.data)
  const pending = waiting.get(message.id)
  if (pending) {
    waiting.delete(message.id)
    if (message.error) pending.reject(message.error)
    else pending.resolve(message.result)
  }
  if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text)
})
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const requestId = ++id
    waiting.set(requestId, { resolve, reject })
    ws.send(JSON.stringify({ id: requestId, method, params }))
  })
}
async function evaluate(expression) {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
// Start tests/contrast_server.py and an isolated Chromium/Edge CDP instance first.
// No credentials, live Qloo/catalog calls, or production fixture endpoints.
const appUrl = process.env.APP_URL ?? 'http://127.0.0.1:8012'
const axeSource = await readFile(new URL('../node_modules/axe-core/axe.min.js', import.meta.url), 'utf8')
const reports = []
async function waitFor(expression) {
  for (let i = 0; i < 100; i++) { if (await evaluate(expression)) return; await pause(100) }
  throw Error('Timed out: ' + expression)
}
async function settle() {
  await evaluate(`(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,50))}scrollTo(0,0);await document.fonts.ready})()`)
  await pause(1200)
}
async function metrics(name, axe = false) {
  const measurement = await evaluate(`(${measureDocument.toString()})(${composite.toString()},${contrast.toString()})`)
  let accessibility = { violations: [], incomplete: [] }
  if (axe) {
    await call('Runtime.evaluate', { expression: axeSource })
    accessibility = await evaluate(`window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}).then(r=>({violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),incomplete:r.incomplete.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))}))`)
  }
  reports.push({ name, ...measurement, accessibility })
  console.log(JSON.stringify({ name, text: measurement.text.length, controls: measurement.controls.length, failures: measurement.failures, axe: accessibility.violations }))
}
async function shot(name, selector) {
  // Stitch a component at its real responsive width, keeping sticky navigation
  // and the profile tray outside the crop rather than covering off-screen text.
  const viewport = await evaluate(`({width:innerWidth,height:innerHeight})`)
  const requiredHeight = await evaluate(`document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect().height + document.querySelector('header').offsetHeight + document.querySelector('#tune').offsetHeight + 48`)
  await call('Emulation.setDeviceMetricsOverride', { width: viewport.width, height: Math.max(viewport.height, Math.ceil(requiredHeight)), deviceScaleFactor: 1, mobile: viewport.width < 600 })
  await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});const top=e.getBoundingClientRect().top+scrollY-document.querySelector('header').offsetHeight-16;scrollTo({top:Math.max(0,top),behavior:'instant'})})()`)
  await pause(100)
  const rect = await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});const r=e.getBoundingClientRect();return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height}})()`)
  const screenshot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { ...rect, scale: 1 } })
  await writeFile(new URL(name + '.png', output), Buffer.from(screenshot.data, 'base64'))
  await call('Emulation.setDeviceMetricsOverride', { ...viewport, deviceScaleFactor: 1, mobile: viewport.width < 600 })
}
await call('Runtime.enable'); await call('Page.enable'); await call('DOM.enable'); await call('CSS.enable')
await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await call('Page.navigate', { url: appUrl }); await waitFor(`!!document.querySelector('[aria-label="After Hours theme"]')`)
for (const theme of ['after-hours', 'daylight']) {
  await evaluate(`localStorage.setItem('crosssignal.profile.v1',JSON.stringify({signals:[{id:'test-film',kind:'entity',name:'Fixture Film',category:'screen',qloo_type:'urn:entity:movie'}],liked:[],disliked:[],prefs:{preferred:['metal'],open_to:['jazz'],avoided:['pop'],eras:['1980s','2000s','2010s'],discovery:'balanced'}}));localStorage.setItem('crosssignal.playlist.v1',JSON.stringify({name:'Contrast test playlist',tracks:[]}));localStorage.setItem('crosssignal.theme.v1',${JSON.stringify(theme)})`)
  await call('Page.reload'); await waitFor(`document.querySelectorAll('.culture-collection').length===5`)
  // Populate the description confirmation panel through actual input/API behavior.
  await evaluate(`document.querySelector('#describe-text').focus()`)
  await call('Input.insertText', { text: 'Fixture Film, metal from the 1980s and 2000s' })
  await evaluate(`[...document.querySelectorAll('#describe button')].find(b=>b.textContent.includes('Read my description')).click()`)
  await waitFor(`document.querySelector('#describe').textContent.includes('Exact match')`)
  for (const width of [1440, 375]) {
    await call('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width < 600 })
    await settle()
    await metrics(`${theme}-${width}-default`, true)
    await shot(`${theme}-${width}-collections`, '.collection-grid')
    await shot(`${theme}-${width}-description`, '#describe')
    await shot(`${theme}-${width}-header`, 'header')
    await shot(`${theme}-${width}-hero`, '#top')
    await shot(`${theme}-${width}-search`, '#culture-search')
    await shot(`${theme}-${width}-sound`, '#sound')
    await evaluate(`document.querySelector('[aria-label="Category"] button:nth-child(3)').click()`)
    await pause(200)
    await metrics(`${theme}-${width}-category-selected`)
    await evaluate(`document.querySelector('[aria-label="Category"] button').click()`)
    if (await evaluate(`document.documentElement.scrollWidth > innerWidth`)) throw Error('Horizontal overflow')
    const documentNode = await call('DOM.getDocument')
    for (const selector of ['.collection-pick', '.category-toggle', '.cs-button[data-variant="accent"]', '.description-example', '.header-control', '.era-toggle[aria-pressed="true"]']) {
      const { nodeId } = await call('DOM.querySelector', { nodeId: documentNode.root.nodeId, selector })
      await call('CSS.forcePseudoState', { nodeId, forcedPseudoClasses: ['hover', 'focus', 'focus-visible'] })
      await pause(200)
      await metrics(`${theme}-${width}-${selector}-hover-focus`)
      if (selector === '.collection-pick') await shot(`${theme}-${width}-collection-hover-focus`, '.culture-collection')
      await call('CSS.forcePseudoState', { nodeId, forcedPseudoClasses: [] })
    }
    await evaluate(`document.querySelectorAll('.collection-pick').forEach(b=>b.disabled=true)`)
    await metrics(`${theme}-${width}-disabled-collection-picks`)
    await shot(`${theme}-${width}-collections-disabled`, '.collection-grid')
    await evaluate(`document.querySelectorAll('.collection-pick').forEach(b=>b.disabled=false)`)
  }
  await evaluate(`[...document.querySelectorAll('#tune button')].find(b=>b.textContent.includes('Tune My Radio')).click()`)
  await waitFor(`document.querySelectorAll('.record-card').length===8`)
  await evaluate(`document.querySelector('button[aria-label^="Add Fixture song"]').click();document.querySelector('.record-card button[aria-expanded]').click()`)
  for (const width of [1440, 375]) {
    await call('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width < 600 })
    await settle(); await metrics(`${theme}-${width}-results-playlist-notification`, true)
    await shot(`${theme}-${width}-recommendation`, '.record-card')
    await shot(`${theme}-${width}-playlist`, '#playlist')
    if (await evaluate(`document.querySelector('#playlist input').getBoundingClientRect().width < 200`)) throw Error('Playlist name field is too narrow')
    if (width === 375) {
      await evaluate(`window.__originalPlay=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=()=>Promise.reject(new Error('Synthetic unavailable-preview test'));document.querySelector('button[aria-label^="Play preview"]').click()`)
      await waitFor(`!!document.querySelector('.now-playing')`)
      await pause(300)
      await metrics(`${theme}-preview-player`, true)
      await shot(`${theme}-preview-player`, '.now-playing')
      await evaluate(`document.querySelector('[aria-label="Close player"]').click();HTMLMediaElement.prototype.play=window.__originalPlay`)
      await waitFor(`!document.querySelector('.now-playing')`)
    }
  }
  // Use real local fixture pages for empty state, without changing the ranker.
  for (let page=2;page<=3;page++) {
    await evaluate(`[...document.querySelectorAll('#radio button')].find(b=>b.textContent.includes('Try another mix')).click()`)
    await waitFor(page===2 ? `document.querySelectorAll('.record-card').length===8&&document.querySelector('.record-card h3').textContent.includes('fixture 8')` : `document.querySelector('#radio').textContent.includes('No new eligible artists on this page')`)
  }
  await metrics(`${theme}-empty`, true)

  // Pause an actual fixture response to inspect the loading presentation.
  let pausedRequest = null
  const loadingListener = e => { const m = JSON.parse(e.data); if (m.method === 'Fetch.requestPaused') pausedRequest = m.params.requestId }
  ws.addEventListener('message', loadingListener)
  await call('Fetch.enable', { patterns: [{ urlPattern: '*/api/discover', requestStage: 'Response' }] })
  await evaluate(`[...document.querySelectorAll('#tune button')].find(b=>b.textContent.includes('Tune My Radio')).click()`)
  for (let i=0;i<60&&!pausedRequest;i++) await pause(100)
  if (!pausedRequest) throw Error('Fixture response was not paused')
  await metrics(`${theme}-loading`, true)
  await shot(`${theme}-loading`, '#radio')
  await call('Fetch.continueRequest', { requestId: pausedRequest })
  await call('Fetch.disable')
  ws.removeEventListener('message', loadingListener)
  await waitFor(`document.querySelectorAll('.record-card').length===8`)
  await settle()
  // An explicitly synthetic network error exercises the app error presentation.
  const errorListener = e => {
    const m = JSON.parse(e.data)
    if (m.method === 'Fetch.requestPaused') void call('Fetch.fulfillRequest', {
      requestId: m.params.requestId, responseCode: 503,
      responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
      body: Buffer.from(JSON.stringify({error:{kind:'unavailable',message:'Synthetic test service is unavailable. Try again.'}})).toString('base64'),
    })
  }
  ws.addEventListener('message', errorListener)
  await call('Fetch.enable', { patterns: [{ urlPattern: '*api/search*', requestStage: 'Request' }] })
  await evaluate(`document.querySelector('#culture-search input').focus()`)
  await call('Input.insertText', { text: 'Fixture error' })
  await waitFor(`document.querySelector('#culture-search').textContent.includes('Synthetic test service')`)
  await pause(500)
  await metrics(`${theme}-error`, true)
  await shot(`${theme}-error`, '#culture-search')
  await call('Fetch.disable'); ws.removeEventListener('message', errorListener)
  // Inspect the native confirmation contract; its colors are browser/OS-owned.
  let dialogText = ''
  const dialogListener = e => { const m=JSON.parse(e.data); if(m.method==='Page.javascriptDialogOpening'){dialogText=m.params.message;void call('Page.handleJavaScriptDialog',{accept:true})} }
  ws.addEventListener('message', dialogListener)
  await evaluate(`[...document.querySelectorAll('.header-control')].find(b=>b.textContent==='Reset').click()`)
  ws.removeEventListener('message', dialogListener)
  if (!dialogText.includes('Your playlist and theme will stay')) throw Error('Reset confirmation missing')
  await pause(100)
  await shot(`${theme}-toast`, '.toast-surface')
  await settle()
  await metrics(`${theme}-reset-notification`, true)
  await shot(`${theme}-reset-notification`, 'header')
}
await writeFile(new URL('report.json', output), JSON.stringify({ reports, errors }, null, 2))
const failures = reports.flatMap(r=>[...r.failures, ...r.accessibility.violations])
console.log(JSON.stringify({ cases: reports.length, failures: failures.length, exceptions: errors, output: output.pathname }))
ws.close()
if(failures.length || errors.length) process.exitCode=1
