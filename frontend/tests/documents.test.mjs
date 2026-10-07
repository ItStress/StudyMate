import assert from 'node:assert/strict'
import test from 'node:test'
import { createModuleLoader } from './moduleLoader.mjs'
import { createHookHarness, deferred, settle } from './hookHarness.mjs'

function pdf(name) {
  const blob = new Blob(['%PDF-1.7\n'])
  return { name, type: 'application/pdf', size: blob.size, slice: (...args) => blob.slice(...args) }
}

async function documentsHarness(initial = []) {
  const hooks = createHookHarness()
  const lists = []
  const uploads = []
  const deletions = []
  const timers = new Map()
  let timerId = 0
  const api = {
    listDocuments(signal) {
      const result = deferred()
      lists.push({ signal, ...result })
      return result.promise
    },
    uploadDocument(file) {
      const result = deferred()
      uploads.push({ file, ...result })
      return result.promise
    },
    deleteDocument(id) {
      const result = deferred()
      deletions.push({ id, ...result })
      return result.promise
    },
  }
  const load = createModuleLoader({
    AbortController, Uint8Array, Error,
    setTimeout(callback, delay) { timers.set(++timerId, { callback, delay }); return timerId },
    clearTimeout(id) { timers.delete(id) },
  }, { react: hooks.react, './api': api })
  const module = await load(new URL('../src/features/documents/usePdfDocuments.ts', import.meta.url))
  await module.evaluate()
  const render = () => hooks.render(module.namespace.usePdfDocuments)
  render()
  lists[0].resolve(initial)
  await settle()
  render()
  return {
    render, lists, uploads, deletions, timers,
    unmount: hooks.unmount,
    tick() {
      const [id, timer] = timers.entries().next().value
      timers.delete(id)
      void timer.callback()
      return timer.delay
    },
  }
}

test('polling ignores list responses started before an upload or deletion', async () => {
  const harness = await documentsHarness([{ id: 'old', filename: 'Old.pdf' }])
  assert.equal(harness.tick(), 2000)
  const upload = harness.render().addFiles([pdf('New.pdf')])
  await settle()
  harness.uploads[0].resolve({ id: 'new', filename: 'New.pdf' })
  await upload
  harness.lists[1].resolve([{ id: 'old', filename: 'Old.pdf' }])
  await settle()
  assert.deepEqual(Array.from(harness.render().documents, (doc) => doc.id), ['new', 'old'])
  assert.equal(harness.render().selectedId, 'new')

  assert.equal(harness.tick(), 3000)
  const removal = harness.render().removeDocument('new')
  harness.deletions[0].resolve()
  await removal
  harness.lists[2].resolve([{ id: 'new' }, { id: 'old' }])
  await settle()
  assert.deepEqual(Array.from(harness.render().documents, (doc) => doc.id), ['old'])
  assert.equal(harness.render().selectedId, null)
  harness.unmount()
})

test('uploads stay sequential, aggregate failures, and select the last successful PDF', async () => {
  const harness = await documentsHarness()
  const upload = harness.render().addFiles([pdf('First.pdf'), pdf('invalid.txt'), pdf('Last.pdf')])
  await settle()
  assert.equal(harness.uploads.length, 1)
  harness.uploads[0].resolve({ id: 'first', filename: 'First.pdf' })
  await settle()
  assert.equal(harness.uploads.length, 2)
  harness.uploads[1].resolve({ id: 'last', filename: 'Last.pdf' })
  await upload
  const state = harness.render()
  assert.deepEqual(Array.from(state.documents, (doc) => doc.id), ['last', 'first'])
  assert.equal(state.selectedId, 'last')
  assert.equal(state.error, 'invalid.txt: Only PDF files are supported.')
  assert.equal(state.isUploading, false)
  harness.unmount()
})

test('unmount cancels polling and prevents rescheduling an in-flight refresh', async () => {
  const harness = await documentsHarness()
  harness.tick()
  harness.unmount()
  assert.equal(harness.lists[0].signal.aborted, true)
  assert.equal(harness.lists[1].signal.aborted, true)
  harness.lists[1].resolve([{ id: 'late' }])
  await settle()
  assert.equal(harness.timers.size, 0)
  assert.equal(harness.render().documents.length, 0)
})

test('failed deletion preserves the selected document and clears the pending flag', async () => {
  const harness = await documentsHarness([{ id: 'pdf-1' }])
  harness.render().selectDocument('pdf-1')
  const removal = harness.render().removeDocument('pdf-1')
  harness.deletions[0].reject(new Error('Database is unavailable'))
  await removal
  const state = harness.render()
  assert.equal(state.selectedId, 'pdf-1')
  assert.equal(state.documents.length, 1)
  assert.equal(state.deletingId, null)
  assert.equal(state.error, 'Database is unavailable')
  harness.unmount()
})
