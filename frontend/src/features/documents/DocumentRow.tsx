import { Spinner } from '../../components/Spinner'
import { Icon } from '../../components/Icon'
import type { PdfDocument } from './types'

type DocumentRowProps = {
  document: PdfDocument
  isSelected: boolean
  isSource: boolean
  deletionDisabled: boolean
  isConfirming: boolean
  setConfirmId: (id: string | null) => void
  onToggleSource: (id: string) => void
  onSelectDocument: (id: string) => void
  onRemoveDocument: (id: string) => void
}

export function DocumentRow({ document, isSelected, isSource, deletionDisabled, isConfirming, setConfirmId, onToggleSource, onSelectDocument, onRemoveDocument }: DocumentRowProps) {
  return (
    <li className={`rounded-xl border ${isSelected ? 'border-accent/40 bg-accent-selected' : 'border-transparent hover:bg-accent-soft'}`}>
      <div className="flex items-start gap-2 p-3">
        <input type="checkbox" checked={isSource} onChange={() => onToggleSource(document.id)} aria-label={`Use ${document.filename} in chat`} className="mt-1 size-4 shrink-0 cursor-pointer accent-accent focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-focus" />
        <button type="button" aria-pressed={isSelected} onClick={() => onSelectDocument(document.id)} className="min-w-0 flex-1 cursor-pointer text-left focus-visible:rounded focus-visible:outline-2 focus-visible:outline-focus">
          <span className="block text-sm font-medium leading-snug [overflow-wrap:anywhere]">{document.filename}</span>
          <span className="mt-1.5 block text-xs tabular-nums text-muted">{document.page_count} {document.page_count === 1 ? 'page' : 'pages'} · {(document.size_bytes / 1024 / 1024).toFixed(1)} MiB</span>
          <span className={`mt-2 inline-flex items-center gap-1.5 text-xs ${document.availability === 'failed' || document.availability === 'no_text' ? 'text-danger' : 'text-accent'}`}>{document.availability === 'waiting' ? <Spinner label={`Preparing ${document.filename} for chat`} /> : <><span className={`size-1.5 rounded-full ${document.availability === 'ready' ? 'bg-accent' : 'bg-danger'}`} />{document.availability === 'ready' ? 'Ready' : document.availability === 'no_text' ? 'No readable text' : 'Preparation failed'}</>}</span>
        </button>
        <button type="button" aria-label={`Remove ${document.filename}`} title={`Remove ${document.filename}`} disabled={deletionDisabled} onClick={() => setConfirmId(document.id)} className="-mr-1 grid size-9 shrink-0 cursor-pointer place-items-center rounded-lg text-muted hover:bg-red-50 hover:text-danger focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50"><Icon name="trash" className="size-4" /></button>
      </div>
      {isConfirming && <div className="border-t border-stroke p-3 text-xs"><p className="leading-relaxed">Remove this PDF from your library?</p><div className="mt-2 flex gap-2"><button type="button" onClick={() => { onRemoveDocument(document.id); setConfirmId(null) }} className="min-h-9 cursor-pointer rounded-md bg-danger px-3 font-semibold text-white focus-visible:outline-2 focus-visible:outline-focus">Remove PDF</button><button type="button" onClick={() => setConfirmId(null)} className="min-h-9 cursor-pointer rounded-md px-3 text-muted hover:bg-paper focus-visible:outline-2 focus-visible:outline-focus">Keep it</button></div></div>}
    </li>
  )
}
