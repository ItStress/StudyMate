export type PdfDocument = {
  id: string
  filename: string
  size_bytes: number
  page_count: number
  sha256: string
  created_at: string
  published: PublishedResult | null
  availability: 'waiting' | 'ready' | 'no_text' | 'failed'
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

export function documentContentUrl(id: string): string {
  return `/api/documents/${id}/content`
}
