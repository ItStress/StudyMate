import { DocumentPanel } from './features/documents/DocumentPanel'
import { PdfPreview } from './features/documents/PdfPreview'
import { usePdfDocuments } from './features/documents/usePdfDocuments'

export default function App() {
  const {
    documents,
    selectedId,
    selectedDocument,
    error,
    addFiles,
    selectDocument,
    removeDocument,
  } = usePdfDocuments()

  return (
    <main className="min-h-screen bg-canvas text-ink">
      <div className="mx-auto max-w-[1440px] px-5 py-7 sm:px-8 sm:py-12 lg:px-[72px]">
        <header className="mb-8">
          <span className="text-xs font-bold tracking-[0.12em] text-eyebrow uppercase">
            Your study space
          </span>
          <h1 className="mt-2 text-4xl font-bold tracking-[-0.045em] sm:text-5xl">StudyMate</h1>
          <p className="mt-2.5 text-base text-muted">
            Add PDFs to view them here. Your files stay in this browser session.
          </p>
        </header>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(270px,340px)_minmax(0,1fr)]">
          <DocumentPanel
            documents={documents}
            selectedId={selectedId}
            error={error}
            onFilesSelected={addFiles}
            onSelectDocument={selectDocument}
            onRemoveDocument={removeDocument}
          />
          <PdfPreview document={selectedDocument} />
        </div>
      </div>
    </main>
  )
}
