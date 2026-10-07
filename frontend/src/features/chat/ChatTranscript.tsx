import type { RefObject, UIEventHandler } from 'react'
import { Icon } from '../../components/Icon'
import { ChatMessageBubble } from './ChatMessageBubble'
import type { ChatAttempt, ChatMessage, Citation } from './types'

type ChatTranscriptProps = {
  transcriptRef: RefObject<HTMLDivElement | null>
  onScroll: UIEventHandler<HTMLDivElement>
  isPending: boolean
  canSend: boolean
  messages: ChatMessage[]
  attempt: ChatAttempt | null
  availableIds: string[]
  onCitation: (citation: Citation) => void
  onPrompt: (prompt: string) => void
}

export function ChatTranscript({ transcriptRef, onScroll, isPending, canSend, messages, attempt, availableIds, onCitation, onPrompt }: ChatTranscriptProps) {
  return (
    <div ref={transcriptRef} onScroll={onScroll} aria-busy={isPending} role="log" aria-label="Chat messages" aria-live="polite" aria-relevant="additions" className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
      {messages.length === 0 && !attempt && (
        <div className="flex h-full min-h-48 flex-col justify-center py-5">
          <h3 className="font-serif text-2xl tracking-[-0.02em]">Turn reading into understanding.</h3>
          <div className="mt-6" />
          {['Summarize the key ideas in my selected PDFs.', 'Explain the main concepts in simple terms.', 'How do the ideas in these PDFs connect?'].map((prompt) => <button key={prompt} type="button" disabled={!canSend} onClick={() => onPrompt(prompt)} className="flex min-h-12 cursor-pointer items-center justify-between gap-3 border-b border-divider py-3 text-left text-sm text-accent hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:text-muted"><span>{prompt}</span><Icon name="arrow" className="size-4 shrink-0" /></button>)}
        </div>
      )}
      {messages.map((message) => <ChatMessageBubble key={message.id} role={message.role} content={message.content}
        citations={message.citations} availableIds={availableIds} onCitation={onCitation} />)}
      {attempt && <ChatMessageBubble role="user" content={attempt.question} />}
      {attempt?.answer && <ChatMessageBubble role="assistant" content={attempt.answer} />}
      {attempt && attempt.status !== 'generating' && (
        <p className="text-xs text-muted">{attempt.status === 'stopped' ? 'Response stopped.' : 'Response incomplete.'} Retry to get a complete answer.</p>
      )}
    </div>
  )
}
