import { DocumentPanel } from './features/documents/DocumentPanel'
import { PdfPreview } from './features/documents/PdfPreview'
import { usePdfDocuments } from './features/documents/usePdfDocuments'
import { ChatPanel } from './features/chat/ChatPanel'
import { useState } from 'react'
import type { Citation } from './features/chat/types'
import { Icon } from './components/Icon'

export default function App() {
  const {
    documents,
    selectedId,
    selectedDocument,
    error,
    isLoading,
    isUploading,
    deletingId,
    addFiles,
    selectDocument,
    removeDocument,
  } = usePdfDocuments()
  const [sourceIds, setSourceIds] = useState<string[]>([])
  const [workspaceView, setWorkspaceView] = useState<'reading' | 'chat'>('reading')
  const [preview, setPreview] = useState({ id: '', page: 1, navigation: 0 })
  const sources = documents.filter((doc) => sourceIds.includes(doc.id)).sort((a, b) => a.id.localeCompare(b.id))

  function openDocument(id: string, page = 1) {
    selectDocument(id)
    setPreview((current) => ({ id, page, navigation: current.navigation + 1 }))
  }

  function openCitation(citation: Citation) {
    openDocument(citation.document_id, citation.page_number)
    setWorkspaceView('reading')
  }

  return (
    <main className="min-h-screen bg-canvas text-ink">
      <a href="#workspace" className="sr-only focus:not-sr-only focus:absolute focus:z-10 focus:rounded-lg focus:bg-accent focus:p-3 focus:text-white">Skip to workspace</a>
      <div className="mx-auto max-w-[1800px] px-4 sm:px-7 lg:px-8">
        <header className="flex h-20 items-center justify-between gap-4 border-b border-stroke">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-accent text-white"><Icon name="book" className="size-6" /></span>
            <h1 className="text-xl font-semibold tracking-[-0.03em]">StudyMate</h1>
          </div>
        </header>
        <div className="flex flex-wrap items-end justify-between gap-3 py-6 sm:py-7">
          <div>
            <h2 className="font-serif text-3xl tracking-[-0.02em] sm:text-4xl">A little more understanding.</h2>
          </div>
        </div>
        <div id="workspace" className="grid items-start gap-5 pb-6 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)_360px] 2xl:grid-cols-[300px_minmax(0,1fr)_400px]">
          <DocumentPanel
            documents={documents}
            selectedId={selectedId}
            error={error}
            isLoading={isLoading}
            isUploading={isUploading}
            deletingId={deletingId}
            sourceIds={sources.map((doc) => doc.id)}
            onToggleSource={(id) => setSourceIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])}
            onFilesSelected={addFiles}
            onSelectDocument={(id) => { openDocument(id); setWorkspaceView('reading') }}
            onRemoveDocument={removeDocument}
          />
          <div className="min-w-0 lg:col-start-2 xl:contents">
            <nav aria-label="Workspace view" className="mb-3 flex gap-1 rounded-xl border border-stroke bg-paper p-1 xl:hidden">
              {(['reading', 'chat'] as const).map((view) => <button key={view} type="button" aria-pressed={workspaceView === view} onClick={() => setWorkspaceView(view)} className={`flex min-h-11 flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg text-sm font-semibold focus-visible:outline-2 focus-visible:outline-focus ${workspaceView === view ? 'bg-accent text-white' : 'text-muted hover:bg-accent-soft'}`}><Icon name={view === 'reading' ? 'book' : 'chat'} className="size-4" />{view === 'reading' ? 'Reading' : 'Chat'}{view === 'chat' && sources.length > 0 && <span className="text-xs">({sources.length})</span>}</button>)}
            </nav>
            <div className={workspaceView === 'reading' ? 'min-w-0' : 'hidden xl:block xl:min-w-0'}>
              <PdfPreview document={selectedDocument} page={preview.id === selectedId ? preview.page : 1} navigation={preview.navigation} />
            </div>
            <div className={workspaceView === 'chat' ? 'min-w-0' : 'hidden xl:block xl:min-w-0'}>
              <ChatPanel key={sources.map((doc) => doc.id).join(',')} sources={sources} documents={documents} onCitation={openCitation} />
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
