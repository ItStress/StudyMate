export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export type ChatHistoryMessage = Pick<ChatMessage, 'role' | 'content'>

export type ChatResponse = {
  answer: string
}
