import { useEffect, useRef, useState } from 'react'
import { streamQuestion } from './api'
import type { ChatMessage } from './types'

type Attempt = { question: string; answer: string; status: 'generating' | 'stopped' | 'failed' }

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [attempt, setAttempt] = useState<Attempt | null>(null)
  const [error, setError] = useState('')
  const activeRequest = useRef<AbortController | null>(null)

  useEffect(() => () => {
    activeRequest.current?.abort()
    activeRequest.current = null
  }, [])

  async function sendMessage(questionToRetry?: string) {
    const question = (questionToRetry ?? draft).trim()
    if (!question || activeRequest.current) return
    const controller = new AbortController()
    activeRequest.current = controller
    setAttempt({ question, answer: '', status: 'generating' })
    setDraft('')
    setError('')

    try {
      const history = messages.slice(-20).map(({ role, content }) => ({ role, content }))
      const answer = await streamQuestion(question, history, controller.signal, (content) => {
        if (activeRequest.current !== controller) return
        setAttempt((current) => current ? { ...current, answer: current.answer + content } : current)
      })
      if (activeRequest.current !== controller) return
      setMessages((current) => [...current,
        { id: crypto.randomUUID(), role: 'user', content: question },
        { id: crypto.randomUUID(), role: 'assistant', content: answer },
      ])
      setAttempt(null)
    } catch (cause: unknown) {
      if (activeRequest.current !== controller || controller.signal.aborted) return
      setAttempt((current) => current ? { ...current, status: 'failed' } : current)
      setDraft(question)
      setError(cause instanceof Error ? cause.message : 'Could not reach the model. Please try again.')
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null
    }
  }

  function stop() {
    activeRequest.current?.abort()
    activeRequest.current = null
    setAttempt((current) => current ? { ...current, status: 'stopped' } : current)
  }

  function retry() {
    if (attempt && attempt.status !== 'generating') void sendMessage(attempt.question)
  }

  function newChat() {
    activeRequest.current?.abort()
    activeRequest.current = null
    setMessages([])
    setAttempt(null)
    setDraft('')
    setError('')
  }

  return { messages, draft, setDraft, attempt, error, sendMessage, stop, retry, newChat }
}
