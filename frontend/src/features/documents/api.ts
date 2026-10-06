import type { PdfDocument } from './types'

async function checkedResponse(response: Response): Promise<Response> {
  if (response.ok) return response

  const body = await response.json().catch(() => null)
  const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status})`
  throw new Error(detail)
}

export async function listDocuments(signal: AbortSignal): Promise<PdfDocument[]> {
  const response = await checkedResponse(await fetch('/api/documents', { signal, cache: 'no-store' }))
  return response.json() as Promise<PdfDocument[]>
}

export async function uploadDocument(file: File): Promise<PdfDocument> {
  const form = new FormData()
  form.append('file', file)
  const response = await checkedResponse(await fetch('/api/documents', {
    method: 'POST',
    body: form,
  }))
  return response.json() as Promise<PdfDocument>
}

export async function deleteDocument(id: string): Promise<void> {
  await checkedResponse(await fetch(`/api/documents/${id}`, { method: 'DELETE' }))
}
