import { useState } from 'react'
import { documentContentUrl, preparedAssetUrl } from './types'
import type { PdfDocument } from './types'
import { usePreparedPage } from './usePreparedPage'
import { PreparedContent } from './PreparedContent'

const buttonStyle = 'cursor-pointer rounded-lg border border-stroke px-3 py-2 text-sm font-semibold hover:bg-accent-soft focus-visible:outline-3 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-40'

export function PreparationInspector({ document }: { document: PdfDocument }) {
  const [selectedPage, setSelectedPage] = useState(1)
  const pageNumber = Math.min(selectedPage, document.page_count)
  const { data, error, reload } = usePreparedPage(document.id, pageNumber, document.published?.id)
  const page = data?.items[0]
  const pending = ['queued', 'processing'].includes(document.preparation.status)

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 border-b border-divider px-5 py-3">
        <button className={buttonStyle} disabled={pageNumber === 1} onClick={() => setSelectedPage(pageNumber - 1)}>Previous</button>
        <label className="flex items-center gap-2 text-sm">
          Physical page
          <input type="number" min={1} max={document.page_count} value={pageNumber}
            onChange={(event) => {
              const value = Number(event.target.value)
              if (Number.isInteger(value) && value >= 1 && value <= document.page_count) setSelectedPage(value)
            }}
            className="w-20 rounded-md border border-stroke px-2 py-1 focus-visible:outline-3 focus-visible:outline-focus" />
          of {document.page_count}
        </label>
        <button className={buttonStyle} disabled={pageNumber === document.page_count} onClick={() => setSelectedPage(pageNumber + 1)}>Next</button>
      </div>
      <div className="grid min-w-0 gap-0 md:grid-cols-2">
        {page?.page_image_id ? <section className="h-[65vh] min-h-[420px] overflow-auto bg-canvas p-3" aria-label="Original physical page">
          <p className="mb-2 text-xs text-subtle">Original physical page {pageNumber} · rendered from the PDF</p>
          <img className="w-full bg-white shadow-sm" src={preparedAssetUrl(document.id, page.page_image_id)} alt={`Original physical page ${pageNumber} of ${document.filename}`} />
        </section> : <iframe key={pageNumber} className="block h-[65vh] min-h-[420px] w-full border-0"
          src={`${documentContentUrl(document.id)}#page=${pageNumber}`} title={`Physical page ${pageNumber} of ${document.filename}`} />}
        <section className="min-w-0 border-t border-divider p-5 md:border-t-0 md:border-l" aria-label="Prepared content">
          <h3 className="font-semibold">Prepared content</h3>
          {document.published && <p className="mt-1 text-xs text-subtle">Extraction version {data?.published.pipeline_version ?? document.published.pipeline_version} · Physical page {pageNumber}</p>}
          {document.published && (pending || document.preparation.status === 'failed') && (
            <p className="mt-3 text-sm text-subtle" role="status">Showing older published results. {pending ? `New preparation: ${document.preparation.status}.` : 'The latest attempt failed.'}</p>
          )}
          {!document.published && <p className="mt-4 text-sm text-subtle" role="status">No published result yet. Preparation is {document.preparation.status}.</p>}
          {error && <div className="mt-4" role="alert"><p className="text-sm text-danger">{error}</p><button onClick={reload} className={`${buttonStyle} mt-2`}>Reload page</button></div>}
          {document.published && !data && !error && <p className="mt-4 text-sm text-subtle" role="status">Loading prepared page…</p>}
          {page && <PreparedContent documentId={document.id} page={page} />}
          {data && !page && <p className="mt-4 text-sm text-danger">This physical page is missing from the published result.</p>}
        </section>
      </div>
    </>
  )
}
