import { useRef } from 'react'
import type { ChangeEvent } from 'react'
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

export function DocumentPanel({
  documents,
  selectedId,
  error,
  isLoading,
  isUploading,
  deletingId,
  sourceIds,
  onToggleSource,
  onFilesSelected,
  onSelectDocument,
  onRemoveDocument,
}: DocumentPanelProps) {
  const fileInput = useRef<HTMLInputElement>(null)

  function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    onFilesSelected(event.currentTarget.files)
    event.currentTarget.value = ''
  }

  return (
    <section
      className="min-w-0 overflow-hidden rounded-[18px] border border-stroke bg-white shadow-panel"
      aria-labelledby="documents-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-divider px-6 py-[22px]">
        <div>
          <h2 id="documents-heading" className="text-lg font-semibold tracking-[-0.02em]">Documents</h2>
          <p className="mt-1 text-[13px] text-subtle">
            {documents.length} {documents.length === 1 ? 'PDF' : 'PDFs'} added
          </p>
        </div>
        <input
          ref={fileInput}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          onChange={handleFileSelection}
          className="hidden"
          aria-label="Choose PDF files"
        />
        <button
          type="button"
          className="cursor-pointer rounded-[9px] bg-accent px-3.5 py-2.5 text-[13px] font-semibold whitespace-nowrap text-white hover:bg-accent-hover focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isLoading || isUploading}
          onClick={() => fileInput.current?.click()}
        >
          {isUploading ? 'Uploading...' : 'Add PDFs'}
        </button>
      </div>

      {error && <p className="mx-6 mt-4 text-[13px] text-danger" role="alert">{error}</p>}

      {documents.length === 0 ? (
        <div className="flex min-h-[260px] flex-col items-center justify-center px-5 py-8 text-center">
          <div
            className="mb-4 grid h-[60px] w-[50px] place-items-center rounded-[7px] bg-accent-soft text-[10px] font-extrabold tracking-[0.03em] text-accent"
            aria-hidden="true"
          >
            PDF
          </div>
          <p className="font-semibold">{isLoading ? 'Loading PDFs...' : 'No PDFs added yet'}</p>
          {!isLoading && <span className="mt-1.5 text-[13px] text-subtle">Choose one or more files to get started.</span>}
        </div>
      ) : (
        <ul className="max-h-[260px] list-none overflow-auto p-2.5 lg:max-h-[65vh]">
          {documents.map((document) => (
            <li key={document.id} className="flex min-w-0 items-center gap-1">
              <input type="checkbox" checked={sourceIds.includes(document.id)}
                onChange={() => onToggleSource(document.id)} aria-label={`Use ${document.filename} in chat`}
                className="ml-2 size-4 shrink-0 cursor-pointer accent-accent focus-visible:outline-2 focus-visible:outline-focus" />
              <button
                type="button"
                className={`flex min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-[10px] p-3 text-left hover:bg-accent-selected focus-visible:outline-3 focus-visible:outline-offset-[-3px] focus-visible:outline-focus ${document.id === selectedId ? 'bg-accent-selected' : ''}`}
                aria-pressed={document.id === selectedId}
                onClick={() => onSelectDocument(document.id)}
              >
                <span
                  className="grid h-[42px] w-[34px] shrink-0 place-items-center rounded-[7px] bg-accent-soft text-[10px] font-extrabold tracking-[0.03em] text-accent"
                  aria-hidden="true"
                >
                  PDF
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{document.filename}</span>
                  <span className="mt-1 block text-xs text-subtle">
                    {document.page_count} {document.page_count === 1 ? 'page' : 'pages'} · {(document.size_bytes / 1024 / 1024).toFixed(1)} MiB
                  </span>
                </span>
              </button>
              <button
                type="button"
                className="grid size-10 shrink-0 cursor-pointer place-items-center rounded-[10px] text-subtle hover:bg-red-50 hover:text-danger focus-visible:outline-3 focus-visible:outline-offset-[-3px] focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={`Remove ${document.filename}`}
                title={`Remove ${document.filename}`}
                disabled={deletingId !== null}
                onClick={() => onRemoveDocument(document.id)}
              >
                <svg
                  aria-hidden="true"
                  className="size-5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M4 6h16M9 6V4h6v2M6 6l1 14h10l1-14M10 10v6M14 10v6" />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
