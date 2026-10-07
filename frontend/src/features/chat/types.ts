export type Citation = {
  number: number
  document_id: string
  filename: string
  page_number: number
  publication_id: string
  chunk_id: string
  excerpt: string
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  grounded?: boolean
}

export type ChatHistoryMessage = Pick<ChatMessage, 'role' | 'content'>

export type ChatResponse = {
  answer: string
  citations: Citation[]
  grounded: boolean
}

export type ChatAttempt = { question: string; answer: string; documentIds: string[]; status: 'generating' | 'stopped' | 'failed' }
