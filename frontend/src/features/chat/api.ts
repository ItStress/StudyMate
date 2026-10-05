import type { ChatHistoryMessage, ChatResponse } from './types'

export async function askQuestion(
  question: string,
  history: ChatHistoryMessage[],
  signal: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history }),
    signal,
  })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}). Please try again.`)
  }
  if (!body || typeof body !== 'object' || !('answer' in body) ||
      typeof body.answer !== 'string' || !body.answer.trim()) {
    throw new Error('The model returned an invalid response. Please try again.')
  }
  return { answer: body.answer }
}
