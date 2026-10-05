import { preparedAssetUrl } from './types'
import type { PreparedPage } from './types'

export function PreparedContent({ documentId, page }: { documentId: string, page: PreparedPage }) {
  const included = page.blocks.filter((block) => !block.excluded)
  const excluded = page.blocks.filter((block) => block.excluded)
  return (
    <div className="mt-4 space-y-4">
      {page.warnings.length > 0 && <ul className="list-disc space-y-1 rounded-lg bg-accent-soft py-3 pr-3 pl-7 text-sm" aria-label="Extraction warnings">
        {page.warnings.map((warning) => <li key={warning}>{warning}</li>)}
      </ul>}
      {!page.has_text && <p className="text-sm text-subtle">No extractable text. Inspect the original PDF.</p>}
      <div className="max-h-[55vh] space-y-4 overflow-auto">
        {included.length === 0 && page.text && <p className="text-sm leading-6 break-words whitespace-pre-wrap">{page.text}</p>}
        {included.map((block) => <article key={block.id} className="min-w-0">
          {block.kind !== 'text' && <h4 className="mb-2 text-xs font-bold tracking-wide text-subtle uppercase">{block.kind}</h4>}
          {block.kind === 'table' && block.rows ? <div className="overflow-x-auto"><table className="w-full border-collapse text-left text-sm">
            <tbody>{block.rows.map((row, index) => <tr key={index}>{row.map((cell, column) => index < (block.header_rows ?? 0)
              ? <th key={column} className="border border-stroke bg-accent-soft p-2 font-semibold">{cell}</th>
              : <td key={column} className="border border-stroke p-2">{cell}</td>)}</tr>)}</tbody>
          </table></div> : block.kind !== 'diagram' && block.text && <p className="text-sm leading-6 break-words whitespace-pre-wrap">{block.text}</p>}
          {block.asset_id && <img className="mt-2 max-w-full rounded-lg border border-stroke" src={preparedAssetUrl(documentId, block.asset_id)} alt={`${block.kind} evidence on physical page ${page.page_number}`} />}
          {block.caption && <p className="mt-2 text-sm text-subtle">Source caption: {block.caption}</p>}
          {block.kind !== 'text' && <p className="mt-1 text-xs text-subtle">Source region: {block.bbox.map((coordinate) => Math.round(coordinate)).join(', ')}</p>}
        </article>)}
      </div>
      {excluded.length > 0 && <details className="text-sm"><summary className="cursor-pointer font-medium">Excluded repeated headers and footers ({excluded.length})</summary>
        {excluded.map((block) => <p key={block.id} className="mt-2 whitespace-pre-wrap text-subtle">{block.text}</p>)}
      </details>}
      {page.page_image_id && <details className="text-sm"><summary className="cursor-pointer font-medium">Full-page visual evidence</summary>
        <img className="mt-3 w-full border border-stroke" src={preparedAssetUrl(documentId, page.page_image_id)} alt={`Visual evidence for physical page ${page.page_number}`} loading="lazy" />
      </details>}
    </div>
  )
}
