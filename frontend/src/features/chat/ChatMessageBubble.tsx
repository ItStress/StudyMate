import type { ChatHistoryMessage, Citation } from './types'
import { documentContentUrl } from '../documents/types'

type Props = ChatHistoryMessage & {
  citations?: Citation[]
  availableIds?: string[]
  onCitation?: (citation: Citation) => void
}

export function ChatMessageBubble({ role, content, citations = [], availableIds = [], onCitation }: Props) {
  const isUser = role === 'user'
  const parts = content.split(/(\[\d+\])/g)
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[92%] min-w-0 rounded-xl px-4 py-3 ${isUser ? 'bg-accent text-white' : 'bg-accent-soft text-ink'}`}>
        <p className={`mb-1 text-xs font-semibold ${isUser ? 'text-white/80' : 'text-muted'}`}>
          {isUser ? 'You' : 'StudyMate'}
        </p>
        <p className="text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]">
          {parts.map((part, index) => {
            const citation = citations.find((item) => `[${item.number}]` === part)
            return citation ? <button key={index} type="button" disabled={!availableIds.includes(citation.document_id)}
              onClick={() => onCitation?.(citation)} title={`${citation.filename}, page ${citation.page_number}`}
              className="mx-0.5 cursor-pointer rounded px-1 font-semibold text-accent underline focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50">
              {part}
            </button> : part
          })}
        </p>
        {citations.map((citation) => <details key={citation.number} className="mt-3 border-t border-stroke pt-2 text-xs">
          <summary className="cursor-pointer font-semibold">[{citation.number}] {citation.filename} · Page {citation.page_number}</summary>
          <p className="mt-2 leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]">{citation.excerpt}</p>
          {availableIds.includes(citation.document_id) ? <div className="mt-2 flex flex-wrap gap-3">
            <button type="button" className="cursor-pointer font-semibold text-accent hover:underline focus-visible:outline-2 focus-visible:outline-focus"
              onClick={() => onCitation?.(citation)}>View page</button>
            <a className="font-semibold text-accent hover:underline focus-visible:outline-2 focus-visible:outline-focus"
              href={`${documentContentUrl(citation.document_id)}#page=${citation.page_number}`} target="_blank" rel="noopener noreferrer">Open PDF</a>
          </div> : <p className="mt-2 text-subtle">This PDF is no longer available.</p>}
        </details>)}
      </div>
    </div>
  )
}
