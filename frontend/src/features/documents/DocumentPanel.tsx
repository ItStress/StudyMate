import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { Spinner } from '../../components/Spinner'
import { Icon } from '../../components/Icon'
import type { PdfDocument } from './types'
import { DocumentRow } from './DocumentRow'

type DocumentPanelProps = {
  documents: PdfDocument[]
  selectedId: string | null
  error: string
  isLoading: boolean
  isUploading: boolean
  deletingId: string | null
  sourceIds: string[]
  onToggleSource: (id: string) => void
  onFilesSelected: (files: FileList | null) => void
  onSelectDocument: (id: string) => void
  onRemoveDocument: (id: string) => void
}

export function DocumentPanel({ documents, selectedId, error, isLoading, isUploading, deletingId, sourceIds, onToggleSource, onFilesSelected, onSelectDocument, onRemoveDocument }: DocumentPanelProps) {
  const fileInput = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const filtered = documents.filter((document) => document.filename.toLowerCase().includes(query.toLowerCase()))

  function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    onFilesSelected(event.currentTarget.files)
    event.currentTarget.value = ''
  }

  return (
    <section className="min-w-0 lg:sticky lg:top-6" aria-labelledby="documents-heading">
      <div className="mb-4 flex items-center justify-between">
        <h2 id="documents-heading" className="text-base font-semibold">Documents <span className="ml-1 text-sm font-normal tabular-nums text-muted">({documents.length})</span></h2>
      </div>
      <input ref={fileInput} type="file" accept=".pdf,application/pdf" multiple onChange={handleFileSelection} className="hidden" aria-label="Choose PDF files" />
      <button type="button" disabled={isLoading || isUploading} onClick={() => fileInput.current?.click()}
        onDragOver={(event) => { event.preventDefault(); if (!isLoading && !isUploading) setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => { event.preventDefault(); setIsDragging(false); if (!isLoading && !isUploading) onFilesSelected(event.dataTransfer.files) }}
        className={`flex w-full cursor-pointer items-center gap-3 rounded-xl border border-dashed p-4 text-left transition-colors focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-60 ${isDragging ? 'border-accent bg-accent-selected' : 'border-accent/40 bg-accent-soft hover:border-accent hover:bg-accent-selected'}`}>
        {isUploading ? <Spinner label="Uploading PDFs" className="size-6" /> : <Icon name="upload" className="size-6 shrink-0 text-accent" />}
        <span><span className="block text-sm font-semibold text-accent">{isUploading ? 'Uploading PDFs…' : 'Add PDFs'}</span><span className="mt-1 block text-xs text-muted">PDF · up to 25 MiB</span></span>
      </button>
      {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm leading-relaxed text-danger" role="alert">{error}</p>}
      {documents.length > 0 && <div className="relative mt-5">
        <Icon name="search" className="pointer-events-none absolute top-3 left-3 size-4 text-muted" />
        <input type="search" aria-label="Search documents" placeholder="Find a document…" value={query} onChange={(event) => setQuery(event.currentTarget.value)} className="h-10 w-full rounded-lg border border-stroke bg-paper pr-3 pl-9 text-sm placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-focus" />
      </div>}
      {documents.length === 0 ? <div className="py-8 text-sm leading-relaxed text-muted"><p className="font-semibold text-ink">{isLoading ? 'Loading your library…' : 'Start with a PDF.'}</p></div> : <>
        <p className="mt-4 mb-2 text-xs leading-relaxed text-muted">Check the PDFs you want to use in chat.</p>
        <ul className="max-h-60 space-y-2 overflow-y-auto lg:max-h-[calc(100dvh-460px)] lg:min-h-40">
          {filtered.map((document) => <DocumentRow key={document.id} document={document}
            isSelected={selectedId === document.id} isSource={sourceIds.includes(document.id)}
            deletionDisabled={deletingId !== null} isConfirming={confirmId === document.id} setConfirmId={setConfirmId}
            onToggleSource={onToggleSource} onSelectDocument={onSelectDocument} onRemoveDocument={onRemoveDocument} />)}
        </ul>
        {filtered.length === 0 && <p role="status" className="py-5 text-sm text-muted">No documents match “{query}”.</p>}
      </>}
      <div className="mt-5 flex items-start gap-2 border-t border-stroke pt-4 text-xs leading-relaxed text-muted"><Icon name="chat" className="mt-0.5 size-4 shrink-0" /><p>{sourceIds.length} {sourceIds.length === 1 ? 'source' : 'sources'} selected</p></div>
    </section>
  )
}
