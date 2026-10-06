import { DocumentPanel } from './features/documents/DocumentPanel'
import { PdfPreview } from './features/documents/PdfPreview'
import { usePdfDocuments } from './features/documents/usePdfDocuments'
import { ChatPanel } from './features/chat/ChatPanel'
import { useState } from 'react'
import type { Citation } from './features/chat/types'

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
  const [preview, setPreview] = useState({ id: '', page: 1, navigation: 0 })
  const sources = documents.filter((doc) => sourceIds.includes(doc.id)).sort((a, b) => a.id.localeCompare(b.id))

  function openDocument(id: string, page = 1) {
    selectDocument(id)
    setPreview((current) => ({ id, page, navigation: current.navigation + 1 }))
  }

  function openCitation(citation: Citation) {
    openDocument(citation.document_id, citation.page_number)
  }

  return (
    <main className="min-h-screen bg-canvas text-ink">
      <div className="mx-auto max-w-[1440px] px-5 py-7 sm:px-8 sm:py-12 lg:px-[72px]">
        <header className="mb-8">
          <span className="text-xs font-bold tracking-[0.12em] text-eyebrow uppercase">
            Your study space
          </span>
          <h1 className="mt-2 text-4xl font-bold tracking-[-0.045em] sm:text-5xl">StudyMate</h1>
          <p className="mt-2.5 text-base text-muted">
            Explore your PDFs and ask your local study assistant a question.
          </p>
        </header>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(240px,280px)_minmax(0,1fr)] xl:grid-cols-[minmax(220px,260px)_minmax(0,1fr)_minmax(320px,380px)]">
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
            onSelectDocument={openDocument}
            onRemoveDocument={removeDocument}
          />
          <PdfPreview document={selectedDocument} page={preview.id === selectedId ? preview.page : 1} navigation={preview.navigation} />
          <div className="min-w-0 lg:col-start-2 xl:col-start-3">
            <ChatPanel key={sources.map((doc) => doc.id).join(',')} sources={sources} documents={documents} onCitation={openCitation} />
          </div>
        </div>
      </div>
    </main>
  )
}
