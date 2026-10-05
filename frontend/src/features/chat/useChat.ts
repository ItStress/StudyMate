import { useEffect, useRef, useState } from 'react'
import { askQuestion } from './api'
import type { ChatMessage } from './types'

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const [error, setError] = useState('')
  const activeRequest = useRef<AbortController | null>(null)

  useEffect(() => () => {
    activeRequest.current?.abort()
    activeRequest.current = null
  }, [])

  async function sendMessage() {
    const question = draft.trim()
    if (!question || activeRequest.current) return
    const controller = new AbortController()
    activeRequest.current = controller
    setPendingQuestion(question)
    setDraft('')
    setError('')

    try {
      const history = messages.slice(-20).map(({ role, content }) => ({ role, content }))
      const { answer } = await askQuestion(question, history, controller.signal)
      if (activeRequest.current !== controller) return
      setMessages((current) => [...current,
        { id: crypto.randomUUID(), role: 'user', content: question },
        { id: crypto.randomUUID(), role: 'assistant', content: answer },
      ])
    } catch (cause: unknown) {
      if (activeRequest.current !== controller || controller.signal.aborted) return
      setDraft(question)
      setError(cause instanceof Error ? cause.message : 'Could not reach the model. Please try again.')
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null
        setPendingQuestion(null)
      }
    }
  }

  function newChat() {
    activeRequest.current?.abort()
    activeRequest.current = null
    setMessages([])
    setPendingQuestion(null)
    setDraft('')
    setError('')
  }

  return { messages, draft, setDraft, pendingQuestion, error, sendMessage, newChat }
}
