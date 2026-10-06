import type { ChatHistoryMessage } from './types'

export async function streamQuestion(
  question: string,
  history: ChatHistoryMessage[],
  signal: AbortSignal,
  onDelta: (content: string) => void,
): Promise<string> {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history }),
    signal,
  })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}). Please try again.`)
  }
  if (!response.body) throw new Error('Streaming is unavailable. Please try again.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let answer = ''
  let completed = false

  function consume(line: string) {
    if (!line.trim()) return
    const event: unknown = JSON.parse(line)
    if (!event || typeof event !== 'object' || !('type' in event) || completed) {
      throw new Error('The model returned an invalid stream. Please try again.')
    }
    if (event.type === 'error') {
      throw new Error('detail' in event && typeof event.detail === 'string'
        ? event.detail : 'The model could not complete the response. Please try again.')
    }
    if (event.type === 'delta' && 'content' in event && typeof event.content === 'string') {
      answer += event.content
      onDelta(event.content)
    } else if (event.type === 'done' && answer.trim()) {
      completed = true
    } else {
      throw new Error('The model returned an invalid stream. Please try again.')
    }
  }

  try {
    while (!completed) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      let newline = buffer.indexOf('\n')
      while (newline !== -1) {
        consume(buffer.slice(0, newline))
        buffer = buffer.slice(newline + 1)
        newline = buffer.indexOf('\n')
      }
      if (done) {
        consume(buffer)
        if (!completed) throw new Error('The response was interrupted. Please retry.')
        break
      }
    }
    return answer.trim()
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
