import { Icon } from '../../components/Icon'
import { documentContentUrl } from './types'
import type { PdfDocument } from './types'

type PdfPreviewProps = { document: PdfDocument | undefined; page: number; navigation: number }

export function PdfPreview({ document, page, navigation }: PdfPreviewProps) {
  return (
    <section className="flex h-[max(480px,calc(100dvh-208px))] min-w-0 flex-col overflow-hidden rounded-xl border border-stroke bg-paper" aria-labelledby="preview-heading">
      <div className="flex min-h-20 items-center justify-between gap-3 border-b border-divider px-5 py-4">
        <div className="min-w-0">
          <h2 id="preview-heading" className="text-sm font-semibold [overflow-wrap:anywhere]">{document?.filename ?? 'Reading space'}</h2>
          {document && <p className="mt-1 text-xs text-muted">{document.page_count} pages</p>}
        </div>
        {document && <a href={`${documentContentUrl(document.id)}#page=${page}`} target="_blank" rel="noopener noreferrer" className="flex min-h-10 shrink-0 items-center gap-2 rounded-lg px-2 text-xs font-semibold text-accent hover:bg-accent-soft focus-visible:outline-2 focus-visible:outline-focus">Open PDF<Icon name="external" className="size-3.5" /></a>}
      </div>
      {document ? <iframe key={`${document.id}:${navigation}`} className="block min-h-0 w-full flex-1 border-0 bg-canvas" src={`${documentContentUrl(document.id)}#page=${page}`} title={`Preview of ${document.filename}`} /> : <div className="flex flex-1 flex-col items-center justify-center bg-canvas/50 px-6 py-10 text-center">
        <Icon name="book" className="mb-6 size-12 text-accent/60" />
        <h3 className="font-serif text-3xl tracking-[-0.02em]">Make room for a new idea.</h3>
        <p className="mt-3 max-w-64 text-sm leading-relaxed text-muted">Select a PDF to start reading.</p>
      </div>}
    </section>
  )
}
