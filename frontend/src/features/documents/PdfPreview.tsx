import { documentContentUrl } from './types'
import type { PdfDocument } from './types'

type PdfPreviewProps = {
  document: PdfDocument | undefined
  page: number
  navigation: number
}

export function PdfPreview({ document, page, navigation }: PdfPreviewProps) {
  return (
    <section
      className="min-w-0 overflow-hidden rounded-[18px] border border-stroke bg-white shadow-panel"
      aria-labelledby="preview-heading"
    >
      <div className="flex min-h-[88px] items-center justify-between gap-4 border-b border-divider px-6 py-[22px]">
        <div className="min-w-0">
          <span className="text-xs font-bold tracking-[0.12em] text-eyebrow uppercase">Preview</span>
          <h2 id="preview-heading" className="mt-1 break-words text-lg font-semibold tracking-[-0.02em]">
            {document?.filename ?? 'Select a PDF'}
          </h2>
        </div>
        {document && (
          <a
            href={`${documentContentUrl(document.id)}#page=${page}`}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-[13px] font-bold text-accent hover:underline focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-focus"
          >
            Open PDF
          </a>
        )}
      </div>
      {document ? (
        <iframe key={`${document.id}:${navigation}`} className="block h-[min(72vh,900px)] min-h-[420px] w-full border-0"
          src={`${documentContentUrl(document.id)}#page=${page}`} title={`Preview of ${document.filename}`} />
      ) : (
        <div className="grid h-[min(72vh,900px)] min-h-[420px] place-items-center p-6 text-center text-sm text-subtle">
          Your selected PDF will appear here.
        </div>
      )}
    </section>
  )
}
