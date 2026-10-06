import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatHistoryMessage, Citation } from './types'
import { documentContentUrl } from '../documents/types'
import { remarkCitations } from './remarkCitations'

type Props = ChatHistoryMessage & {
  citations?: Citation[]
  availableIds?: string[]
  onCitation?: (citation: Citation) => void
}

export function ChatMessageBubble({ role, content, citations = [], availableIds = [], onCitation }: Props) {
  const isUser = role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-full min-w-0 rounded-xl px-4 py-3 ${isUser ? 'bg-accent text-white' : 'w-full bg-canvas text-ink'}`}>
        <p className={`mb-2 text-xs font-semibold ${isUser ? 'text-white/80' : 'text-muted'}`}>
          {isUser ? 'You' : 'StudyMate'}
        </p>
        {isUser ? <p className="text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]">{content}</p> :
          <div className="text-sm leading-relaxed [overflow-wrap:anywhere] [&_p]:my-3 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_h1]:mt-5 [&_h1]:mb-2 [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:mt-5 [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mt-4 [&_h3]:mb-2 [&_h3]:text-base [&_h3]:font-semibold [&_h4]:mt-4 [&_h4]:font-semibold [&_h5]:mt-4 [&_h5]:font-semibold [&_h6]:mt-4 [&_h6]:font-semibold [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-1 [&_li>p]:my-1 [&_strong]:font-semibold [&_blockquote]:my-3 [&_blockquote]:border-l [&_blockquote]:border-accent/40 [&_blockquote]:pl-3 [&_blockquote]:text-muted [&_code]:rounded [&_code]:bg-accent-soft [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-accent-soft [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_hr]:my-4 [&_hr]:border-stroke [&_input]:accent-accent">
            <Markdown skipHtml remarkPlugins={[remarkGfm, [remarkCitations, { numbers: citations.map((citation) => citation.number) }]]}
              components={{
                a: ({ href, children }) => {
                  const citation = citations.find((item) => href === `#studymate-citation-${item.number}`)
                  return citation ? <button type="button" disabled={!availableIds.includes(citation.document_id)}
                    onClick={() => onCitation?.(citation)} title={`${citation.filename}, page ${citation.page_number}`}
                    className="mx-0.5 cursor-pointer rounded px-1 font-semibold text-accent underline focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50">
                    {children}
                  </button> : <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent underline focus-visible:outline-2 focus-visible:outline-focus">{children}</a>
                },
                table: ({ children }) => <div className="my-3 max-w-full overflow-x-auto"><table className="w-full border-collapse text-left text-xs">{children}</table></div>,
                th: ({ children }) => <th className="border border-stroke bg-accent-soft px-3 py-2 font-semibold">{children}</th>,
                td: ({ children }) => <td className="border border-stroke px-3 py-2 align-top">{children}</td>,
                img: ({ alt }) => <span>{alt}</span>,
              }}>
              {content}
            </Markdown>
          </div>}
        {citations.map((citation) => <details key={citation.number} className="mt-3 border-t border-stroke pt-2 text-xs">
          <summary className="cursor-pointer font-semibold [overflow-wrap:anywhere]">[{citation.number}] {citation.filename} · Page {citation.page_number}</summary>
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
