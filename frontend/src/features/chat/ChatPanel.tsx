import { useEffect, useRef } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { ChatMessageBubble } from './ChatMessageBubble'
import { useChat } from './useChat'

export function ChatPanel() {
  const { messages, draft, setDraft, pendingQuestion, error, sendMessage, newChat } = useChat()
  const transcript = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const isPending = pendingQuestion !== null

  useEffect(() => {
    const container = transcript.current
    if (container) container.scrollTop = container.scrollHeight
  }, [messages, pendingQuestion])

  useEffect(() => {
    if (!isPending) input.current?.focus()
  }, [isPending])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void sendMessage()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <section className="flex h-[min(72vh,900px)] min-h-[520px] min-w-0 flex-col overflow-hidden rounded-[18px] border border-stroke bg-white shadow-panel xl:h-[calc(min(72vh,900px)+88px)]" aria-labelledby="chat-heading">
      <div className="flex min-h-[88px] items-center justify-between gap-3 border-b border-divider px-5 py-5">
        <div>
          <h2 id="chat-heading" className="text-lg font-semibold tracking-[-0.02em]">Chat</h2>
          <p className="mt-1 text-xs text-subtle">Ask your local study assistant.</p>
        </div>
        <button type="button" onClick={() => { newChat(); input.current?.focus() }}
          disabled={messages.length === 0 && !isPending && !draft && !error}
          className="shrink-0 cursor-pointer rounded-lg px-2 py-2 text-xs font-semibold text-accent hover:bg-accent-soft focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50">
          New chat
        </button>
      </div>
      <p className="border-b border-divider px-5 py-3 text-xs leading-relaxed text-muted">
        General questions only. Uploaded PDFs are not used yet.
      </p>
      <div ref={transcript} role="log" aria-label="Chat messages" aria-live="polite" aria-relevant="additions" className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        {messages.length === 0 && !isPending && (
          <div className="flex h-full min-h-32 flex-col items-center justify-center text-center">
            <p className="font-semibold">What would you like to learn?</p>
            <p className="mt-2 text-sm text-subtle">Ask a question to start a conversation.</p>
          </div>
        )}
        {messages.map((message) => <ChatMessageBubble key={message.id} role={message.role} content={message.content} />)}
        {pendingQuestion !== null && <ChatMessageBubble role="user" content={pendingQuestion} />}
      </div>
      <p role="status" className={`px-5 text-xs text-muted ${isPending ? 'pb-3' : 'sr-only'}`}>
        {isPending ? 'Generating response…' : ''}
      </p>
      {error && <p role="alert" className="px-5 pb-3 text-sm text-danger">{error}</p>}
      <form onSubmit={submit} className="border-t border-divider p-4">
        <label htmlFor="chat-question" className="sr-only">Your question</label>
        <textarea ref={input} id="chat-question" rows={3} value={draft} disabled={isPending}
          onChange={(event) => setDraft(event.currentTarget.value)} onKeyDown={handleKeyDown}
          placeholder="Ask a question…"
          className="block w-full resize-none rounded-lg border border-stroke bg-canvas px-3 py-2.5 text-sm leading-relaxed focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-60" />
        <div className="mt-3 flex items-center justify-between gap-3">
          <span className="text-[11px] text-subtle">Shift + Enter for a new line</span>
          <button type="submit" disabled={isPending || !draft.trim()}
            className="cursor-pointer rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-hover focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50">
            Send
          </button>
        </div>
      </form>
    </section>
  )
}
