import { useEffect, useRef } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { Spinner } from '../../components/Spinner'
import { Icon } from '../../components/Icon'
import { ChatTranscript } from './ChatTranscript'
import { ChatComposer } from './ChatComposer'
import { useChat } from './useChat'
import type { Citation } from './types'
import type { PdfDocument } from '../documents/types'

type ChatPanelProps = {
  sources: PdfDocument[]
  documents: PdfDocument[]
  onCitation: (citation: Citation) => void
}

export function ChatPanel({ sources, documents, onCitation }: ChatPanelProps) {
  const isPreparing = sources.some((document) => document.availability === 'waiting')
  const unavailableSources = sources.filter((document) => document.availability === 'failed' || document.availability === 'no_text')
  const canSend = sources.length > 0 && sources.every((document) => document.availability === 'ready')
  const { messages, draft, setDraft, attempt, error, sendMessage, stop, retry, newChat } = useChat(sources.map((doc) => doc.id), canSend)
  const availableIds = documents.map((doc) => doc.id)
  const transcript = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const followResponse = useRef(true)
  const wasPending = useRef(false)
  const isPending = attempt?.status === 'generating'

  useEffect(() => {
    const container = transcript.current
    if (container && followResponse.current) container.scrollTop = container.scrollHeight
  }, [messages, attempt])

  useEffect(() => {
    if (wasPending.current && !isPending) input.current?.focus()
    wasPending.current = isPending
  }, [isPending])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    followResponse.current = true
    void sendMessage()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <section className="flex h-[max(480px,calc(100dvh-208px))] min-w-0 flex-col overflow-hidden rounded-xl border border-stroke bg-paper" aria-labelledby="chat-heading">
      <div className="flex min-h-20 items-center justify-between gap-3 border-b border-divider px-5 py-4">
        <div>
          <h2 id="chat-heading" className="flex items-center gap-2 text-sm font-semibold"><Icon name="chat" className="size-4 text-accent" />Study assistant</h2>
        </div>
        <button type="button" onClick={() => { followResponse.current = true; newChat(); input.current?.focus() }}
          disabled={messages.length === 0 && !attempt && !draft && !error}
          className="shrink-0 cursor-pointer min-h-10 rounded-lg px-2 py-2 text-xs font-semibold text-accent hover:bg-accent-soft focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50">
          New chat
        </button>
      </div>
      {isPreparing && <div className="flex justify-center border-b border-divider py-3"><Spinner label="Preparing selected PDFs for chat" /></div>}
      {unavailableSources.length > 0 && <div role="alert" className="border-b border-divider px-5 py-3 text-xs leading-relaxed text-danger">
        {unavailableSources.map((doc) => <p key={doc.id} className="[overflow-wrap:anywhere]">{doc.filename}: {doc.availability === 'no_text' ? 'No readable text. Use a text-based PDF or run OCR.' : 'Preparation failed. Remove this source from chat or upload it again.'}</p>)}
      </div>}
      <ChatTranscript transcriptRef={transcript} onScroll={(event) => {
        const container = event.currentTarget
        followResponse.current = container.scrollHeight - container.scrollTop - container.clientHeight < 64
      }} isPending={isPending} canSend={canSend} messages={messages} attempt={attempt}
        availableIds={availableIds} onCitation={onCitation} onPrompt={(prompt) => { setDraft(prompt); input.current?.focus() }} />
      {isPending && <div className="px-5 pb-3"><Spinner label={attempt?.answer ? 'Generating response' : 'Preparing response'} /></div>}
      <p role="status" className="sr-only">{!isPending && (attempt ? 'Response interrupted.' : messages.length ? 'Response complete.' : '')}</p>
      {error && <p role="alert" className="px-5 pb-3 text-sm text-danger">{error}</p>}
      {attempt && (
        <div className="flex gap-2 px-5 pb-3">
          <button type="button" onClick={() => { if (isPending) stop(); else { followResponse.current = true; retry() } }}
            disabled={!isPending && !canSend}
            className="cursor-pointer rounded-lg border border-stroke px-3 py-2 text-xs font-semibold text-accent hover:bg-accent-soft focus-visible:outline-2 focus-visible:outline-focus">
            {isPending ? 'Stop' : 'Retry'}
          </button>
        </div>
      )}
      <ChatComposer inputRef={input} onSubmit={submit} onKeyDown={handleKeyDown} onDraftChange={setDraft}
        draft={draft} isPending={isPending} canSend={canSend} isPreparing={isPreparing} />
    </section>
  )
}
