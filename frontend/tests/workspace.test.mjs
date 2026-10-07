import assert from 'node:assert/strict'
import test from 'node:test'
import { createModuleLoader } from './moduleLoader.mjs'
import { createHookHarness } from './hookHarness.mjs'

async function workspaceHarness() {
  const hooks = createHookHarness()
  const selections = []
  const documents = [{ id: 'b' }, { id: 'a' }]
  const load = createModuleLoader({}, {
    react: hooks.react,
    '../documents/usePdfDocuments': { usePdfDocuments: () => ({ documents, selectDocument: (id) => selections.push(id) }) },
  })
  const module = await load(new URL('../src/features/workspace/useWorkspace.ts', import.meta.url))
  await module.evaluate()
  return { documents, selections, render: () => hooks.render(module.namespace.useWorkspace) }
}

test('workspace derives sorted existing sources and preserves the chat key across document refreshes', async () => {
  const harness = await workspaceHarness()
  harness.render().toggleSource('b')
  harness.render().toggleSource('a')
  const key = () => harness.render().sources.map((doc) => doc.id).join(',')
  assert.equal(key(), 'a,b')
  harness.documents.reverse()
  harness.documents[0] = { ...harness.documents[0], availability: 'ready' }
  assert.equal(key(), 'a,b')
  harness.documents.splice(harness.documents.findIndex((doc) => doc.id === 'a'), 1)
  assert.equal(key(), 'b')
  harness.render().toggleSource('b')
  assert.equal(key(), '')
})

test('citations open physical pages in reading view and repeated navigation reloads the preview', async () => {
  const harness = await workspaceHarness()
  harness.render().setWorkspaceView('chat')
  const citation = { document_id: 'a', page_number: 3 }
  harness.render().openCitation(citation)
  let state = harness.render()
  assert.equal(state.workspaceView, 'reading')
  assert.equal(state.preview.id, 'a')
  assert.equal(state.preview.page, 3)
  assert.equal(state.preview.navigation, 1)
  state.openCitation(citation)
  state = harness.render()
  assert.equal(state.preview.navigation, 2)
  state.openDocument('b')
  state = harness.render()
  assert.equal(state.preview.id, 'b')
  assert.equal(state.preview.page, 1)
  assert.equal(state.preview.navigation, 3)
  assert.deepEqual(harness.selections, ['a', 'a', 'b'])
})
