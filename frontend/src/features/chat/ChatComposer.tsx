import type { FormEventHandler, KeyboardEventHandler, RefObject } from 'react'
import { Icon } from '../../components/Icon'

type ChatComposerProps = {
  inputRef: RefObject<HTMLTextAreaElement | null>
  onSubmit: FormEventHandler<HTMLFormElement>
  onKeyDown: KeyboardEventHandler<HTMLTextAreaElement>
  onDraftChange: (draft: string) => void
  draft: string
  isPending: boolean
  canSend: boolean
  isPreparing: boolean
}

export function ChatComposer({ inputRef, onSubmit, onKeyDown, onDraftChange, draft, isPending, canSend, isPreparing }: ChatComposerProps) {
  return (
    <form onSubmit={onSubmit} className="border-t border-divider p-4">
      <label htmlFor="chat-question" className="sr-only">Your question</label>
      <textarea ref={inputRef} id="chat-question" rows={2} value={draft} disabled={isPending || !canSend} maxLength={2000}
        onChange={(event) => onDraftChange(event.currentTarget.value)} onKeyDown={onKeyDown}
        placeholder={canSend ? 'Ask about your PDFs…' : isPreparing ? 'Preparing PDFs…' : 'Select PDFs for chat…'}
        className="block w-full resize-none rounded-lg border border-stroke bg-canvas px-3 py-2.5 text-sm leading-relaxed placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-60" />
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-[11px] text-subtle">Shift + Enter for a new line</span>
        <button type="submit" disabled={isPending || !draft.trim() || !canSend}
          className="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-hover focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50">
          Send<Icon name="arrow" className="size-4" />
        </button>
      </div>
    </form>
  )
}
