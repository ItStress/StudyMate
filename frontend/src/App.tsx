import { DocumentPanel } from './features/documents/DocumentPanel'
import { PdfPreview } from './features/documents/PdfPreview'
import { useWorkspace } from './features/workspace/useWorkspace'
import { WorkspaceNavigation } from './features/workspace/WorkspaceNavigation'
import { ChatPanel } from './features/chat/ChatPanel'
import { Icon } from './components/Icon'

export default function App() {
  const {
    documents, selectedId, selectedDocument, error, isLoading, isUploading, deletingId,
    addFiles, removeDocument, sources, workspaceView, setWorkspaceView, preview,
    openDocument, openCitation, toggleSource,
  } = useWorkspace()

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
            onToggleSource={toggleSource}
            onFilesSelected={addFiles}
            onSelectDocument={(id) => { openDocument(id); setWorkspaceView('reading') }}
            onRemoveDocument={removeDocument}
          />
          <div className="min-w-0 lg:col-start-2 xl:contents">
            <WorkspaceNavigation workspaceView={workspaceView} sourceCount={sources.length} onChange={setWorkspaceView} />
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
