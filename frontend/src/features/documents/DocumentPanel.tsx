import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { Spinner } from '../../components/Spinner'
import { Icon } from '../../components/Icon'
import type { PdfDocument } from './types'

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
          {filtered.map((document) => <li key={document.id} className={`rounded-xl border ${selectedId === document.id ? 'border-accent/40 bg-accent-selected' : 'border-transparent hover:bg-accent-soft'}`}>
            <div className="flex items-start gap-2 p-3">
              <input type="checkbox" checked={sourceIds.includes(document.id)} onChange={() => onToggleSource(document.id)} aria-label={`Use ${document.filename} in chat`} className="mt-1 size-4 shrink-0 cursor-pointer accent-accent focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-focus" />
              <button type="button" aria-pressed={document.id === selectedId} onClick={() => onSelectDocument(document.id)} className="min-w-0 flex-1 cursor-pointer text-left focus-visible:rounded focus-visible:outline-2 focus-visible:outline-focus">
                <span className="block text-sm font-medium leading-snug [overflow-wrap:anywhere]">{document.filename}</span>
                <span className="mt-1.5 block text-xs tabular-nums text-muted">{document.page_count} {document.page_count === 1 ? 'page' : 'pages'} · {(document.size_bytes / 1024 / 1024).toFixed(1)} MiB</span>
                <span className={`mt-2 inline-flex items-center gap-1.5 text-xs ${document.availability === 'failed' || document.availability === 'no_text' ? 'text-danger' : 'text-accent'}`}>{document.availability === 'waiting' ? <Spinner label={`Preparing ${document.filename} for chat`} /> : <><span className={`size-1.5 rounded-full ${document.availability === 'ready' ? 'bg-accent' : 'bg-danger'}`} />{document.availability === 'ready' ? 'Ready' : document.availability === 'no_text' ? 'No readable text' : 'Preparation failed'}</>}</span>
              </button>
              <button type="button" aria-label={`Remove ${document.filename}`} title={`Remove ${document.filename}`} disabled={deletingId !== null} onClick={() => setConfirmId(document.id)} className="-mr-1 grid size-9 shrink-0 cursor-pointer place-items-center rounded-lg text-muted hover:bg-red-50 hover:text-danger focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50"><Icon name="trash" className="size-4" /></button>
            </div>
            {confirmId === document.id && <div className="border-t border-stroke p-3 text-xs"><p className="leading-relaxed">Remove this PDF from your library?</p><div className="mt-2 flex gap-2"><button type="button" onClick={() => { onRemoveDocument(document.id); setConfirmId(null) }} className="min-h-9 cursor-pointer rounded-md bg-danger px-3 font-semibold text-white focus-visible:outline-2 focus-visible:outline-focus">Remove PDF</button><button type="button" onClick={() => setConfirmId(null)} className="min-h-9 cursor-pointer rounded-md px-3 text-muted hover:bg-paper focus-visible:outline-2 focus-visible:outline-focus">Keep it</button></div></div>}
          </li>)}
        </ul>
        {filtered.length === 0 && <p role="status" className="py-5 text-sm text-muted">No documents match “{query}”.</p>}
      </>}
      <div className="mt-5 flex items-start gap-2 border-t border-stroke pt-4 text-xs leading-relaxed text-muted"><Icon name="chat" className="mt-0.5 size-4 shrink-0" /><p>{sourceIds.length} {sourceIds.length === 1 ? 'source' : 'sources'} selected</p></div>
    </section>
  )
}
