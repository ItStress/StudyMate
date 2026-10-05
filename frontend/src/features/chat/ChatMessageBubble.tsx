import type { ChatHistoryMessage } from './types'

export function ChatMessageBubble({ role, content }: ChatHistoryMessage) {
  const isUser = role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[92%] min-w-0 rounded-xl px-4 py-3 ${isUser ? 'bg-accent text-white' : 'bg-accent-soft text-ink'}`}>
        <p className={`mb-1 text-xs font-semibold ${isUser ? 'text-white/80' : 'text-muted'}`}>
          {isUser ? 'You' : 'StudyMate'}
        </p>
        <p className="text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]">{content}</p>
      </div>
    </div>
  )
}
