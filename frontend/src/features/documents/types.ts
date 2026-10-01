export type PdfDocument = {
  id: string
  filename: string
  size_bytes: number
  page_count: number
  sha256: string
  created_at: string
}

export function documentContentUrl(id: string): string {
  return `/api/documents/${id}/content`
}
