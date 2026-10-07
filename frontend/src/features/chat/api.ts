import type { ChatHistoryMessage, ChatResponse } from './types'
import { readAnswerStream } from './stream'

export async function streamQuestion(
  question: string,
  history: ChatHistoryMessage[],
  signal: AbortSignal,
  onDelta: (content: string) => void,
  documentIds: string[],
): Promise<ChatResponse> {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history, document_ids: documentIds }),
    signal,
  })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    let message = typeof detail === 'string' ? detail : `Request failed (${response.status}). Please try again.`
    if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') {
      message = detail.message
      if ('documents' in detail && Array.isArray(detail.documents)) {
        message += ' ' + detail.documents.map((doc) => `${doc.filename}: ${doc.reason}`).join('; ')
      }
    }
    throw new Error(message)
  }
  return readAnswerStream(response, onDelta, documentIds)
}
