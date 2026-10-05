export type PdfDocument = {
  id: string
  filename: string
  size_bytes: number
  page_count: number
  sha256: string
  created_at: string
  published: PublishedResult | null
  preparation: {
    status: 'queued' | 'processing' | 'ready' | 'ready_with_warnings' | 'no_text' | 'failed'
    phase: 'waiting' | 'extracting' | 'chunking' | 'complete'
    pages_processed: number
    chunk_count: number
    empty_pages: number[]
    error: string | null
  }
}

export type PublishedResult = {
  id: string
  pipeline_version: string
  status: 'ready' | 'ready_with_warnings' | 'no_text'
  page_count: number
  chunk_count: number
  empty_pages: number[]
  published_at: string
}

export type PreparedPage = {
  document_id: string
  page_number: number
  text: string
  has_text: boolean
  blocks: ContentBlock[]
  warnings: string[]
  page_image_id: string | null
}

export type ContentBlock = {
  id: string
  kind: 'text' | 'table' | 'equation' | 'diagram'
  text: string
  bbox: [number, number, number, number]
  excluded: boolean
  asset_id: string | null
  rows?: string[][]
  header_rows?: number
  caption?: string
}

export function preparedAssetUrl(documentId: string, assetId: string): string {
  return `/api/documents/${documentId}/assets/${assetId}`
}

export type PageResults = {
  items: PreparedPage[]
  total: number
  offset: number
  limit: number
  published: PublishedResult
}

export function documentContentUrl(id: string): string {
  return `/api/documents/${id}/content`
}
