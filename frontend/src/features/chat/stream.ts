import type { ChatResponse, Citation } from './types'

function validCitation(value: unknown): value is Citation {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return Number.isInteger(item.number) && Number(item.number) > 0 &&
    Number.isInteger(item.page_number) && Number(item.page_number) > 0 &&
    ['document_id', 'filename', 'publication_id', 'chunk_id', 'excerpt'].every((key) => typeof item[key] === 'string')
}

export async function readAnswerStream(
  response: Response,
  onDelta: (content: string) => void,
  documentIds: string[],
): Promise<ChatResponse> {
  if (!response.body) throw new Error('Streaming is unavailable. Please try again.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let answer = ''
  let completed = false
  let citations: Citation[] = []
  let grounded = false

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
    } else if (event.type === 'done' && answer.trim() && 'citations' in event &&
        Array.isArray(event.citations) && event.citations.every(validCitation) &&
        'grounded' in event && typeof event.grounded === 'boolean') {
      citations = event.citations
      grounded = event.grounded
      if (citations.some((citation) => !documentIds.includes(citation.document_id))) {
        throw new Error('The response cited a PDF outside the selected sources. Please retry.')
      }
      const numbers = new Set(citations.map((citation) => citation.number))
      const used = [...answer.matchAll(/\[(\d+)\]/g)].map((match) => Number(match[1]))
      if (numbers.size !== citations.length || (grounded && (!citations.length || !used.length ||
          used.some((number) => !numbers.has(number)))) || (!grounded && (citations.length || used.length))) {
        throw new Error('The response contains invalid citations. Please retry.')
      }
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
    return { answer: answer.trim(), citations, grounded }
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
