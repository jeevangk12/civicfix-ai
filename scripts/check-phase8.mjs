import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const [origin, api, fixtureFile, reportFile] = process.argv.slice(2)
if (!origin || !api || !fixtureFile || !reportFile) throw new Error('Usage: node scripts/check-phase8.mjs origin api-base fixture.json report.json')
const url = origin.replace(/\/$/, '')
const scratch = dirname(resolve(fixtureFile))
const fixture = JSON.parse(readFileSync(fixtureFile, 'utf8'))
const { admin, staff, outside, citizen, other, tag, latitude, longitude, department_id: dept } = fixture
const profile = join(scratch, 'civicfix-phase8-chrome-' + process.pid)
mkdirSync(profile, { recursive: true })
const browser = spawn(process.env.CHROME_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--no-sandbox', '--disable-background-networking', '--no-first-run', '--remote-debugging-port=0',
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--user-data-dir=' + profile, 'about:blank',
], { windowsHide: true, stdio: 'ignore' })
const pending = new Map()
const exceptions = []
const loaded = []
const paused = []
let holdScene = false
let tileCount = 0
const tile = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7YQAAAAASUVORK5CYII='
let socket
let next = 0

async function wait(test, label, timeout = 15000) {
  const end = Date.now() + timeout
  let failure
  while (Date.now() < end) {
    try {
      if (await test()) return
    } catch (error) { failure = error.message }
    await delay(100)
  }
  const note = socket?.readyState === 1 ? await evaluate('document.querySelector("main")?.innerText.slice(0, 900)') : null
  throw new Error([label, failure, note].filter(Boolean).join(' | '))
}
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++next
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(method + ' timed out')) }, 15000)
    pending.set(id, (message) => {
      clearTimeout(timer)
      if (message.error) reject(new Error(method + ': ' + message.error.message))
      else resolve(message.result)
    })
    socket.send(JSON.stringify({ id, method, params }))
  })
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text)
  return result.result.value
}
function run(fn, ...args) { return evaluate('(' + fn.toString() + ')(' + args.map(JSON.stringify).join(',') + ')') }
const contains = (txt) => run((text) => document.querySelector('main')?.innerText.includes(text), txt)
const heading = (txt) => wait(() => run((text) => document.querySelector('main h1')?.textContent === text, txt), 'Heading: ' + txt)
async function visit(path) { await send('Page.navigate', { url: url + path }) }
async function view(width, height) { await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width <= 420 }) }
async function shot(name) {
  const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  writeFileSync(join(scratch, 'civicfix-phase8-' + name + '.png'), Buffer.from(result.data, 'base64'))
}
async function click(label, element = 'button') {
  await run((txt, selector) => {
    const target = [...document.querySelectorAll(selector)].find((node) =>
      (node.getAttribute('aria-label') || node.textContent.trim()) === txt && !node.disabled)
    if (!target) throw new Error('Missing control: ' + txt)
    target.click()
  }, label, element)
}
async function fill(section, values) {
  await wait(() => run((name) => name === null ? !!document.querySelector('form') :
    [...document.querySelectorAll('section')].some((node) =>
      node.querySelector('h2')?.textContent === name && node.querySelector('form')), section), 'Form: ' + section)
  await run((title, values) => {
    const single = [...document.querySelectorAll('section')].find((item) => item.querySelector('h2')?.textContent === title)
    const form = (single ?? document).querySelector('form')
    if (!form) throw new Error('Missing form: ' + title)
    for (const [key, value] of Object.entries(values)) {
      const options = [...form.querySelectorAll('input, select, textarea')]
      const node = options.find((item) => item.name === key || [...item.labels ?? []].some((label) => label.textContent.trim().startsWith(key)))
      if (!node) throw new Error('Missing field: ' + key)
      if (node.type === 'checkbox') {
        const match = options.find((item) => item.name === key && item.value === value)
        if (!match) throw new Error('Missing checkbox: ' + key)
        if (!match.checked) match.click()
      } else {
        node.value = value
        node.dispatchEvent(new Event('input', { bubbles: true }))
        node.dispatchEvent(new Event('change', { bubbles: true }))
      }
    }
  }, section, values)
}
async function signIn(user, title) {
  await heading('Sign in')
  await fill(null, { email: user.email, password: user.password })
  await click('Sign in')
  await heading(title)
}
async function signOut() { await click('Sign out'); await heading('Sign in') }
async function action(section, fields, button, feedback) {
  await fill(section, fields)
  await click(button)
  await wait(() => contains(feedback), feedback)
  await wait(() => run((name) => [...document.querySelectorAll('section h2')].some((node) => node.textContent === name), section), 'Updated section: ' + section)
}
async function access(user) {
  const r = await fetch(api + '/auth/login', {
    method: 'POST', headers: { 'content-type': 'application/json', 'X-CivicFix-CSRF': '1', origin: url },
    body: JSON.stringify({ email: user.email, password: user.password }),
  })
  assert.equal(r.status, 200)
  return { authorization: 'Bearer ' + (await r.json()).data.access_token }
}

try {
  const portFile = join(profile, 'DevToolsActivePort')
  await wait(() => existsSync(portFile), 'Chrome startup')
  const port = readFileSync(portFile, 'utf8').trim().split(/\r?\n/)[0]
  const tabs = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json()
  socket = new WebSocket(tabs.find((tab) => tab.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }) })
  socket.addEventListener('message', ({ data }) => {
    const packet = JSON.parse(data)
    if (packet.id) {
      const handler = pending.get(packet.id)
      pending.delete(packet.id)
      handler?.(packet)
    }
    if (packet.method === 'Fetch.requestPaused') {
      const { requestId, request } = packet.params
      if (request.url.includes('phase8-tile.png')) {
        tileCount++
        void send('Fetch.fulfillRequest', {
          requestId, responseCode: 200, responseHeaders: [{ name: 'Content-Type', value: 'image/png' }], body: tile,
        }).catch(() => {})
      } else if (holdScene) paused.push(requestId)
      else void send('Fetch.continueRequest', { requestId }).catch(() => {})
    }
    if (packet.method === 'Runtime.exceptionThrown') exceptions.push(packet.params.exceptionDetails.text)
    if (packet.method === 'Network.responseReceived') loaded.push([packet.params.response.status, packet.params.response.url])
  })
  await Promise.all([send('Runtime.enable'), send('Page.enable'), send('Network.enable')])

  await send('Fetch.enable', { patterns: [{ urlPattern: '*phase8-tile.png*' }, { urlPattern: '*SmartCityScene*' }] })
  const animation = () => evaluate('document.querySelector(".city-visual[data-mode=live] canvas")?.width > 100')
  const poster = () => evaluate('document.querySelector(".city-visual[data-mode=still] .city-poster")?.naturalWidth > 100')
  const hero = () => evaluate('!!document.querySelector("#hero-title") && getComputedStyle(document.querySelector(".hero-actions")).opacity === "1"')
  const fits = () => evaluate('document.documentElement.scrollWidth <= innerWidth')
  const metrics = {}

  async function key(name) {
    const code = { Tab: 9, Enter: 13 }[name]
    const params = { key: name, code: name, windowsVirtualKeyCode: code, nativeVirtualKeyCode: code }
    await send('Input.dispatchKeyEvent', { ...params, type: 'rawKeyDown' })
    await send('Input.dispatchKeyEvent', { ...params, type: 'keyUp' })
  }

  async function tabTo(selector) {
    for (let count = 0; count < 24; count++) {
      await key('Tab')
      if (await run((target) => document.activeElement.matches(target), selector)) {
        assert.equal(await evaluate('getComputedStyle(document.activeElement).outlineColor'), 'rgb(255, 179, 77)')
        assert.ok(await evaluate('parseFloat(getComputedStyle(document.activeElement).outlineOffset) >= 3'))
        return
      }
    }
    throw new Error('Tab did not reach ' + selector)
  }

  async function nav(href, title) {
    await run((path) => document.querySelector('nav a[href="' + path + '"]').click(), href)
    await heading(title)
  }

  async function resumeScene() {
    holdScene = false
    for (const requestId of paused.splice(0)) {
      await send('Fetch.continueRequest', { requestId }).catch(() => {})
    }
  }

  async function openHome(query) {
    await visit('/?' + query)
    await wait(() => run((value) => location.search === '?' + value, query), 'Homepage navigation')
    await wait(hero, 'Hero actions ready', 25000)
  }

  async function request(path, { headers = {}, method = 'GET', body, expected = 200 } = {}) {
    const response = await fetch(api + path, {
      method, headers: { ...headers, ...(body === undefined ? {} : { 'content-type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    assert.equal(response.status, expected, method + ' ' + path)
    return (await response.json()).data
  }

  await view(1440, 900)
  await openHome('desktop')
  await wait(animation, 'Desktop WebGL scene', 25000)
  assert.ok(await fits())
  assert.equal(await evaluate('getComputedStyle(document.querySelector("#hero-title")).color'), 'rgb(250, 247, 242)')
  assert.match(await evaluate('getComputedStyle(document.querySelector(".hero-actions .button-primary")).backgroundImage'),
    /255, 179, 77.*255, 122, 26/)
  await tabTo('.hero-actions .button-primary')
  await shot('desktop-home')

  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
  await openHome('reduced-motion')
  await wait(poster, 'Reduced motion poster')
  assert.equal(await evaluate('!!document.querySelector(".city-visual canvas")'), false)

  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
  const injection = await send('Page.addScriptToEvaluateOnNewDocument', {
    source: `const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(kind, ...args) {
        return /webgl/i.test(kind) ? null : original.call(this, kind, ...args)
      }`,
  })
  await openHome('without-webgl')
  await wait(poster, 'WebGL unavailable poster')
  assert.equal(await evaluate('!!document.querySelector(".city-visual canvas")'), false)
  await send('Page.removeScriptToEvaluateOnNewDocument', { identifier: injection.identifier })

  await view(390, 844)
  await send('Network.setCacheDisabled', { cacheDisabled: true })
  await send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: 200000, uploadThroughput: 93750 })
  await send('Emulation.setCPUThrottlingRate', { rate: 4 })
  await openHome('mobile-timing')
  metrics.hero_ready_ms = Math.round(await evaluate('performance.now()'))
  assert.ok(await fits())
  await wait(animation, 'Mobile WebGL scene', 35000)
  metrics.scene_ready_ms = Math.round(await evaluate('performance.now()'))
  metrics.navigation = await evaluate(`(() => {
    const nav = performance.getEntriesByType("navigation")[0]
    return { response_end_ms: Math.round(nav.responseEnd), dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd) }
  })()`)
  await shot('mobile-home')
  await send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
  await send('Emulation.setCPUThrottlingRate', { rate: 1 })

  holdScene = true
  await openHome('loading-map')
  await wait(() => paused.length > 0, 'Deferred city module')
  await wait(poster, 'Poster during import')
  await click('Explore Public Map', '.hero-actions a')
  await heading('Public complaint map')
  await resumeScene()

  holdScene = true
  await openHome('loading-report')
  await wait(() => paused.length > 0, 'Deferred city for report navigation')
  await wait(poster, 'Poster before report navigation')
  await tabTo('.hero-actions .button-primary')
  await key('Enter')
  await heading('Sign in')
  await resumeScene()
  await send('Network.setCacheDisabled', { cacheDisabled: false })
  console.log('Desktop and mobile homepage, amber focus, reduced motion, WebGL fallback, and both hero links while loading passed.')
  console.log('Mobile timing (390×844, 150 ms latency, 1.6 Mbps down, 0.75 Mbps up, 4× CPU): ' + JSON.stringify(metrics))

  await click('Create a citizen account', 'a')
  await heading('Create a citizen account')
  await fill(null, { full_name: citizen.full_name, email: citizen.email, password: citizen.password })
  await click('Create account')
  await heading('Report an issue')
  await tabTo('input[name="title"]')
  assert.ok(await fits())
  await shot('mobile-form')
  await view(1440, 900)
  await tabTo('textarea[name="description"]')
  assert.ok(await fits())
  assert.equal(await evaluate('getComputedStyle(document.querySelector(".workspace")).backgroundColor'), 'rgb(20, 19, 17)')
  await shot('desktop-form')

  const title = 'Leaking supply pipe ' + tag
  const privateLocation = 'Synthetic private access gate ' + tag
  await fill(null, { title, description: 'Water is pooling at a cracked supply pipe alongside the road.',
    latitude: String(latitude), longitude: String(longitude), location_label: privateLocation })
  await click('Submit report')
  await heading(title)
  const reportPath = await evaluate('location.pathname')
  const reportId = reportPath.split('/').at(-1)
  const reference = await evaluate('document.querySelector(".workspace-case-meta code").textContent')
  assert.match(reference, /^CF-/)
  await signOut()

  await signIn(staff, 'Complaint queue')
  await wait(() => contains(reference), 'Scoped water-leak report')
  await run((id) => document.querySelector('a[href="/authority/complaints/' + id + '"]').click(), reportId)
  await heading(title)
  await wait(() => contains('Water pooling around a broken supply pipe.'), 'Mocked AI recommendation')
  assert.ok(await contains('Staff-confirmed values'))
  await action('Change status', { 'New status': 'UNDER_REVIEW', reason: 'Verified the water-service incident.' },
    'Update status', 'Status updated.')
  await wait(() => contains('Assign complaint'), 'Assignment panel')
  await fill('Assignment', { Department: dept })
  await action('Assignment', { 'Staff member': staff.id, reason: 'The crew covers the reported location.' },
    'Assign complaint', 'Assignment saved.')
  await action('Confirm priority', { priority: 'MEDIUM', reason: 'Crew isolated the supply locally.' }, 'Save priority', 'Priority confirmed.')
  await action('Change status', { 'New status': 'IN_PROGRESS', reason: 'Crew arrived and isolated the leak.' },
    'Update status', 'Status updated.')
  const sharedUpdate = 'The crew isolated the failed pipe and began repairs.'
  const privateNote = 'Synthetic staff-only dispatch code ' + tag
  await action('Add progress or note', { visibility: 'PUBLIC', message: sharedUpdate }, 'Save update', 'Update saved.')
  await wait(() => contains(sharedUpdate), 'Public update persisted')
  await action('Add progress or note', { visibility: 'INTERNAL', message: privateNote }, 'Save update', 'Update saved.')
  await wait(() => contains(privateNote), 'Internal note persisted')
  await fill('Change status', { 'New status': 'RESOLVED' })
  await action('Change status', { reason: 'Crew confirmed the replacement joint passed pressure testing.',
    resolution: 'Replaced damaged pipe and verified service.', public_message: 'The water leak was repaired.' },
    'Update status', 'Status updated.')
  await wait(() => contains('Replaced damaged pipe and verified service.'), 'Staff resolution')
  await signOut()

  await signIn(citizen, 'Citizen dashboard')
  await nav('/citizen/notifications', 'Notifications')
  await wait(() => contains('Report resolved'), 'Resolution notice')
  const noticeId = await run(() => [...document.querySelectorAll('[data-notification-id]')].find((item) =>
    item.querySelector('h2')?.textContent === 'Report resolved').dataset.notificationId)
  await click('Open report · Report resolved', 'a')
  await heading(title)
  assert.equal(await evaluate('location.pathname'), reportPath)
  await wait(() => contains(sharedUpdate), 'Dated public update')
  assert.equal(await contains(privateNote), false)
  assert.ok(await evaluate('document.querySelectorAll(".workspace-history time[datetime]").length >= 6'))
  await action('Resolution feedback', { rating: '5', comment: 'Water service was restored.' }, 'Submit feedback', 'Feedback submitted.')
  await nav('/citizen/notifications', 'Notifications')
  await wait(() => contains('Report resolved'), 'Reload resolution notice')
  await click('Mark as read · Report resolved')
  await wait(() => contains('4 unread'), 'Read count updated')

  await visit('/citizen/complaints/new')
  await heading('Report an issue')
  await fill(null, { title: 'Gemini timeout ' + tag, description: 'Synthetic complaint for timeout recovery and optional photo failure.',
    latitude: String(latitude), longitude: String(longitude) })
  await evaluate(`(async () => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 8
    canvas.getContext('2d').fillRect(0, 0, 8, 8)
    const image = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
    const files = new DataTransfer()
    files.items.add(new File([image], 'fixture.png', { type: 'image/png' }))
    const input = document.querySelector('input[name=photo]')
    input.files = files.files
    input.dispatchEvent(new Event('change', { bubbles: true }))
  })()`)
  await click('Submit report')
  await heading('Report submitted')
  await wait(() => contains('Photo storage is temporarily unavailable.'), 'Cloudinary error shown')
  const timeoutRef = await evaluate('document.querySelector("main strong").textContent')
  assert.match(timeoutRef, /^CF-/)
  await click('Continue without photo')
  await heading('Gemini timeout ' + tag)
  const timeoutId = (await evaluate('location.pathname')).split('/').at(-1)
  assert.ok(loaded.some(([status, path]) => status === 503 && path.endsWith('/complaints/' + timeoutId + '/images')))
  await signOut()

  await signIn(other, 'Citizen dashboard')
  await visit(reportPath)
  await wait(() => contains('Resource not found.'), 'Second citizen denied')
  assert.equal(await contains('Resolution feedback'), false)
  await signOut()

  await signIn(admin, 'Users')
  await nav('/admin/audit-logs', 'Audit history')
  await fill(null, { entity_id: reportId })
  await click('Filter audit history')
  const actions = ['COMPLAINT_REVIEWED', 'COMPLAINT_ASSIGNED', 'COMPLAINT_PRIORITY_CHANGED', 'COMPLAINT_NOTE_ADDED', 'COMPLAINT_STATUS_CHANGED']
  await wait(() => run((actions, staffName, reportId) => actions.every((action) => [...document.querySelectorAll('tr[data-action]')].some(
    (row) => row.dataset.action === action && row.innerText.includes(staffName) && row.innerText.includes(reportId) &&
      row.querySelector('time')?.dateTime.endsWith('Z'))), actions, staff.full_name, reportId), 'Admin audit actors and timestamps')
  await shot('audit')

  const ownerHeaders = await access(citizen)
  const secondHeaders = await access(other)
  const staffHeaders = await access(staff)
  const outsideHeaders = await access(outside)
  const timeout = await request('/authority/complaints/' + timeoutId + '/analysis', { headers: staffHeaders })
  assert.equal(timeout.status, 'FAILED')
  const timeoutReport = await request('/complaints/' + timeoutId, { headers: ownerHeaders })
  assert.equal(timeoutReport.public_reference, timeoutRef)
  assert.equal(timeoutReport.status, 'SUBMITTED')
  await request('/notifications/' + noticeId, { headers: secondHeaders, expected: 404 })
  await request('/complaints/' + reportId + '/feedback', {
    method: 'POST', headers: secondHeaders, body: { rating: 5 }, expected: 404,
  })
  await request('/complaints/' + reportId + '/updates', { headers: outsideHeaders, expected: 404 })
  await request('/authority/complaints/' + reportId + '/priority', {
    method: 'PATCH', headers: outsideHeaders, body: { priority: 'HIGH', reason: 'Outside permitted area.' }, expected: 404,
  })

  const approximate = await request('/complaints', { headers: secondHeaders, method: 'POST', expected: 201, body: {
    title: 'Synthetic private details ' + tag,
    description: 'A second fixture tests approved approximate map locations.',
    latitude, longitude, location_label: privateLocation,
  } })
  const approved = 'Water leak near the junction ' + tag
  await request('/authority/complaints/' + approximate.id + '/updates', {
    headers: staffHeaders, method: 'POST', expected: 201, body: { message: privateNote, visibility: 'INTERNAL' },
  })
  await request('/authority/complaints/' + approximate.id + '/visibility', {
    headers: staffHeaders, method: 'PATCH', body: {
      visibility: 'APPROXIMATE', approved_public_summary: approved, reason: 'Approved an approximate public location.',
    },
  })
  const markers = await request('/public/complaints/map?page_size=100')
  assert.ok(markers.every((item) => item.public_reference !== reference))
  const marker = markers.find((item) => item.public_reference === approximate.public_reference)
  assert.ok(marker)
  assert.deepEqual(Object.keys(marker).sort(), [
    'public_reference', 'title', 'category', 'status', 'latitude', 'longitude', 'location_precision', 'created_on', 'updated_on',
  ].sort())
  assert.equal(marker.location_precision, 'approximate')
  assert.equal(marker.title, approved)
  assert.notDeepEqual([marker.latitude, marker.longitude], [latitude, longitude])
  for (const secret of [privateLocation, privateNote, citizen.email, other.email, other.full_name, approximate.title]) {
    assert.ok(!JSON.stringify(markers).includes(secret))
  }
  await request('/public/complaints/' + reference, { expected: 404 })
  await visit('/map')
  await heading('Public complaint map')
  await wait(() => contains(approved), 'Approved report in accessible public list')
  await wait(() => tileCount > 0, 'Mocked Leaflet tiles requested')
  assert.equal(await contains(reference), false)
  assert.deepEqual(exceptions, [])
  writeFileSync(reportFile, JSON.stringify({
    id: reportId, reference, timeout_reference: timeoutRef, public_reference: approximate.public_reference, mobile: metrics,
  }, null, 2))
  console.log('Browser workflow passed for ' + reference + '. Staff audit, recipient feedback, both permission denials, and map redaction passed.')
  console.log('Gemini timeout and Cloudinary outage passed for ' + timeoutRef + '. The report remained submitted without a photo.')
} finally {
  socket?.close()
  browser.kill()
}
