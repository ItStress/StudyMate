import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

async function loadModule(file, globals, imports = {}) {
  const source = await readFile(new URL(`../src/features/chat/${file}`, import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  })
  const context = vm.createContext(globals)
  const module = new vm.SourceTextModule(outputText, { context })
  await module.link((specifier) => {
    const exports = imports[specifier]
    const dependency = new vm.SyntheticModule(Object.keys(exports), function () {
      for (const [name, value] of Object.entries(exports)) this.setExport(name, value)
    }, { context })
    return dependency
  })
  await module.evaluate()
  return module.namespace
}

function response(events, chunkSize = 1) {
  const bytes = new TextEncoder().encode(events.map((event) => JSON.stringify(event)).join('\n') + '\n')
  return new Response(new ReadableStream({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.slice(i, i + chunkSize))
      controller.close()
    },
  }))
}

async function api(fetch) {
  return loadModule('api.ts', { fetch, TextDecoder, Error })
}

test('client forwards history and decodes UTF-8 and NDJSON across arbitrary boundaries', async () => {
  let request
  const client = await api(async (url, options) => {
    request = { url, options }
    return response([{ type: 'delta', content: 'Gravità 😊\n' }, { type: 'delta', content: 'Second line' }, { type: 'done', citations: [], grounded: false }])
  })
  const controller = new AbortController()
  const history = [{ role: 'user', content: 'Hello' }]
  const deltas = []
  const answer = await client.streamQuestion('Explain', history, controller.signal, (delta) => deltas.push(delta), ['pdf-1'])
  assert.equal(answer.answer, 'Gravità 😊\nSecond line')
  assert.deepEqual(deltas, ['Gravità 😊\n', 'Second line'])
  assert.equal(request.url, '/api/chat/stream')
  assert.deepEqual(JSON.parse(request.options.body), { question: 'Explain', history, document_ids: ['pdf-1'] })
  assert.equal(request.options.signal, controller.signal)
})

test('client rejects timeout, malformed events, and streams missing completion', async () => {
  for (const events of [
    [{ type: 'error', status: 504, detail: 'The language model timed out' }],
    [{ type: 'delta', content: 'Partial' }],
    [{ type: 'delta', content: 42 }],
    [{ type: 'done', citations: [], grounded: false }],
    [{ type: 'unknown' }],
  ]) {
    const client = await api(async () => response(events))
    await assert.rejects(client.streamQuestion('Explain', [], new AbortController().signal, () => {}, ['pdf-1']))
  }
  const client = await api(async () => new Response('not JSON'))
  await assert.rejects(client.streamQuestion('Explain', [], new AbortController().signal, () => {}, ['pdf-1']))
})

test('client reports HTTP and network errors and propagates abort', async () => {
  const http = await api(async () => new Response(JSON.stringify({ detail: 'Invalid question' }), { status: 422 }))
  await assert.rejects(http.streamQuestion('Explain', [], new AbortController().signal, () => {}, ['pdf-1']), /Invalid question/)
  const network = await api(async () => { throw new Error('Network unavailable') })
  await assert.rejects(network.streamQuestion('Explain', [], new AbortController().signal, () => {}, ['pdf-1']), /Network unavailable/)
  const aborted = await api(async (_, { signal }) => {
    signal.throwIfAborted()
  })
  const controller = new AbortController()
  controller.abort()
  await assert.rejects(aborted.streamQuestion('Explain', [], controller.signal, () => {}, ['pdf-1']), { name: 'AbortError' })
})

async function hookHarness() {
  const cells = []
  const cleanups = []
  const requests = []
  let cursor = 0
  const react = {
    useState(initial) {
      const index = cursor++
      if (!(index in cells)) cells[index] = initial
      return [cells[index], (value) => {
        cells[index] = typeof value === 'function' ? value(cells[index]) : value
      }]
    },
    useRef(initial) {
      const index = cursor++
      if (!(index in cells)) cells[index] = { current: initial }
      return cells[index]
    },
    useEffect(effect) {
      const index = cursor++
      if (!(index in cells)) {
        cells[index] = true
        cleanups.push(effect())
      }
    },
  }
  const client = {
    streamQuestion(question, history, signal, onDelta, documentIds) {
      return new Promise((resolve, reject) => requests.push({ question, history, signal, onDelta, documentIds, resolve: (answer) => resolve({ answer, citations: [], grounded: false }), reject }))
    },
  }
  const module = await loadModule('useChat.ts', { AbortController, crypto: globalThis.crypto, Error }, {
    react, './api': client,
  })
  return {
    requests,
    render(documentIds = ['pdf-1'], canSend = true) { cursor = 0; return module.useChat(documentIds, canSend) },
    unmount() { for (const cleanup of cleanups) cleanup?.() },
  }
}

test('hook prevents duplicate requests and only confirms completed exchanges', async () => {
  const harness = await hookHarness()
  let chat = harness.render()
  await chat.sendMessage()
  assert.equal(harness.requests.length, 0)
  chat.setDraft(' First question ')
  chat = harness.render()
  const pending = chat.sendMessage()
  await chat.sendMessage()
  assert.equal(harness.requests.length, 1)
  harness.requests[0].onDelta('Partial')
  assert.equal(harness.render().attempt.answer, 'Partial')
  assert.equal(harness.render().messages.length, 0)
  harness.requests[0].resolve('Completed answer')
  await pending
  chat = harness.render()
  assert.equal(chat.messages.length, 2)
  assert.equal(chat.attempt, null)
  chat.setDraft('Follow-up')
  const followup = harness.render().sendMessage()
  assert.deepEqual(JSON.parse(JSON.stringify(harness.requests[1].history)), [
    { role: 'user', content: 'First question' }, { role: 'assistant', content: 'Completed answer' },
  ])
  harness.requests[1].resolve('Follow-up answer')
  await followup
})

test('Stop keeps partial text, Retry excludes it, and late events cannot modify the new attempt', async () => {
  const harness = await hookHarness()
  harness.render().setDraft('Question')
  const first = harness.render().sendMessage()
  harness.requests[0].onDelta('Partial')
  harness.render().stop()
  let chat = harness.render()
  assert.equal(chat.attempt.answer, 'Partial')
  assert.equal(chat.attempt.status, 'stopped')
  assert.equal(harness.requests[0].signal.aborted, true)
  chat.retry()
  assert.equal(harness.requests.length, 2)
  assert.equal(harness.requests[1].history.length, 0)
  harness.requests[0].onDelta('Late')
  harness.requests[0].resolve('Late answer')
  await first
  assert.equal(harness.render().attempt.answer, '')
  harness.requests[1].onDelta('New answer')
  harness.requests[1].resolve('New answer')
  await new Promise((resolve) => setImmediate(resolve))
  chat = harness.render()
  assert.equal(chat.messages.length, 2)
  assert.equal(chat.messages[1].content, 'New answer')
})

test('failed questions are editable and Retry reuses the original question', async () => {
  const harness = await hookHarness()
  harness.render().setDraft('Question')
  const pending = harness.render().sendMessage()
  harness.requests[0].onDelta('Partial')
  harness.requests[0].reject(new Error('The language model timed out'))
  await pending
  let chat = harness.render()
  assert.equal(chat.error, 'The language model timed out')
  assert.equal(chat.draft, 'Question')
  assert.equal(chat.messages.length, 0)
  chat.setDraft('Edited question')
  chat = harness.render()
  chat.retry()
  assert.equal(harness.requests[1].question, 'Question')
  harness.requests[1].resolve('Answer')
  await new Promise((resolve) => setImmediate(resolve))
})

test('New chat and unmount abort pending requests and ignore late answers', async () => {
  for (const action of ['newChat', 'unmount']) {
    const harness = await hookHarness()
    harness.render().setDraft('Question')
    const pending = harness.render().sendMessage()
    if (action === 'newChat') harness.render().newChat()
    else harness.unmount()
    assert.equal(harness.requests[0].signal.aborted, true)
    harness.requests[0].onDelta('Late text')
    harness.requests[0].resolve('Late answer')
    await pending
    assert.equal(harness.render().messages.length, 0)
    if (action === 'newChat') assert.equal(harness.render().attempt, null)
  }
})

test('client confirms server citations and rejects unknown or duplicate labels', async () => {
  const citation = { number: 1, document_id: 'pdf-1', filename: 'biology.pdf', page_number: 2,
    publication_id: 'publication-1', chunk_id: 'chunk-1', excerpt: 'Plants use sunlight.' }
  const client = await api(async () => response([{ type: 'delta', content: 'Plants use sunlight [1].' },
    { type: 'done', grounded: true, citations: [citation] }]))
  const result = await client.streamQuestion('Explain', [], new AbortController().signal, () => {}, ['pdf-1'])
  assert.equal(result.citations[0].page_number, 2)
  assert.equal(result.grounded, true)
  for (const citations of [[], [citation, citation], [{ ...citation, number: 2 }], [{ ...citation, page_number: 0 }]]) {
    const invalid = await api(async () => response([{ type: 'delta', content: 'Answer [1]' },
      { type: 'done', grounded: true, citations }]))
    await assert.rejects(invalid.streamQuestion('Explain', [], new AbortController().signal, () => {}, ['pdf-1']))
  }
})

test('hook blocks unavailable sources and Retry retains the source snapshot', async () => {
  const harness = await hookHarness()
  harness.render().setDraft('Question')
  await harness.render([], false).sendMessage()
  await harness.render(['pdf-1'], false).sendMessage()
  assert.equal(harness.requests.length, 0)
  const pending = harness.render(['pdf-1', 'pdf-2']).sendMessage()
  harness.render().stop()
  harness.render(['pdf-3']).retry()
  assert.deepEqual(Array.from(harness.requests[1].documentIds), ['pdf-1', 'pdf-2'])
  harness.requests[0].resolve('Late')
  await pending
  harness.requests[1].resolve('Completed')
  await new Promise((resolve) => setImmediate(resolve))
})
