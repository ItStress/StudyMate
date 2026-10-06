import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const context = vm.createContext({})
const modules = new Map()
async function loadModule(url) {
  const key = url.href
  if (modules.has(key)) return modules.get(key)
  const source = await readFile(url, 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  })
  const module = new vm.SourceTextModule(outputText, { context })
  modules.set(key, module)
  await module.link(async (specifier) => {
    if (specifier.startsWith('.')) {
      return loadModule(new URL(`${specifier}${['types', 'remarkCitations', 'useChat', 'api'].some((name) => specifier.endsWith(name)) ? '.ts' : '.tsx'}`, url))
    }
    if (modules.has(specifier)) return modules.get(specifier)
    const exports = await import(specifier)
    const dependency = new vm.SyntheticModule(Object.keys(exports), function () {
      for (const [name, value] of Object.entries(exports)) this.setExport(name, value)
    }, { context })
    modules.set(specifier, dependency)
    return dependency
  })
  return module
}
const module = await loadModule(new URL('../src/features/chat/ChatMessageBubble.tsx', import.meta.url))
await module.evaluate()
const { ChatMessageBubble } = module.namespace
const citation = { number: 1, document_id: 'pdf-1', filename: 'Course.pdf', page_number: 3, excerpt: 'Source excerpt' }
function render(content, props = {}) {
  return renderToStaticMarkup(createElement(ChatMessageBubble, { role: 'assistant', content, citations: [citation], availableIds: ['pdf-1'], ...props }))
}

test('answers render headings, emphasis, nested lists, tables, and verified citation buttons', () => {
  const html = render('## Key ideas\n\n**Bold** and *italic* [1]\n\n1. First\n2. Second\n   - Detail\n\n| Topic | Meaning |\n| --- | --- |\n| A | B |')
  for (const tag of ['h2', 'strong', 'em', 'ol', 'ul', 'table', 'th', 'td']) assert.match(html, new RegExp(`<${tag}[ >]`))
  assert.match(html, /<button[^>]*title="Course.pdf, page 3"[^>]*>\[1\]<\/button>/)
})

test('citation markers in code and ordinary Markdown links are not converted into buttons', () => {
  const html = render('`[1]`\n\n```js\nconst reference = "[1]"\n```\n\n[1](https://example.com) and [99]')
  assert.match(html, /<code[^>]*>\[1\]<\/code>/)
  assert.match(html, /<pre[^>]*><code/)
  assert.match(html, /href="https:\/\/example.com"/)
  assert.match(html, /\[99\]/)
  assert.doesNotMatch(html, /<button[^>]*>\[1\]<\/button>/)
})

test('answers do not execute HTML, dangerous URLs, or remote images', () => {
  const html = render('<script>alert(1)</script>\n\n[bad](javascript:alert%281%29)\n\n![diagram](https://example.com/tracker.png)')
  assert.doesNotMatch(html, /<script|href="javascript:|<img/)
  assert.match(html, /diagram/)
})

test('user messages stay literal and citations for removed documents are disabled', () => {
  assert.match(render('**literal**', { role: 'user' }), /\*\*literal\*\*/)
  assert.match(render('Reference [1]', { availableIds: [] }), /<button[^>]*disabled=""[^>]*title="Course.pdf, page 3"/)
})

const panelModule = await loadModule(new URL('../src/features/chat/ChatPanel.tsx', import.meta.url))
await panelModule.evaluate()
const { ChatPanel } = panelModule.namespace
function renderPanel(availability) {
  const document = { id: 'pdf-1', filename: 'Course.pdf', availability }
  return renderToStaticMarkup(createElement(ChatPanel, { sources: [document], documents: [document], onCitation: () => {} }))
}

test('preparing PDFs show an accessible spinner instead of a waiting sentence', () => {
  const html = renderPanel('waiting')
  assert.match(html, /motion-safe:animate-spin/)
  assert.match(html, /Preparing selected PDFs for chat/)
  assert.doesNotMatch(html, /Not available yet|Please wait/)
  assert.match(html, /<textarea[^>]*disabled=""/)
})

test('failed PDFs show recovery instructions rather than an indefinite spinner', () => {
  const html = renderPanel('failed')
  assert.match(html, /Preparation failed/)
  assert.match(html, /Remove this source from chat or upload it again/)
  assert.doesNotMatch(html, /motion-safe:animate-spin/)
})
