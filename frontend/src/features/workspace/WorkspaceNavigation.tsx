import { Icon } from '../../components/Icon'
import type { WorkspaceView } from './types'

type WorkspaceNavigationProps = {
  workspaceView: WorkspaceView
  sourceCount: number
  onChange: (view: WorkspaceView) => void
}

export function WorkspaceNavigation({ workspaceView, sourceCount, onChange }: WorkspaceNavigationProps) {
  return (
    <nav aria-label="Workspace view" className="mb-3 flex gap-1 rounded-xl border border-stroke bg-paper p-1 xl:hidden">
      {(['reading', 'chat'] as const).map((view) => <button key={view} type="button" aria-pressed={workspaceView === view} onClick={() => onChange(view)} className={`flex min-h-11 flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg text-sm font-semibold focus-visible:outline-2 focus-visible:outline-focus ${workspaceView === view ? 'bg-accent text-white' : 'text-muted hover:bg-accent-soft'}`}><Icon name={view === 'reading' ? 'book' : 'chat'} className="size-4" />{view === 'reading' ? 'Reading' : 'Chat'}{view === 'chat' && sourceCount > 0 && <span className="text-xs">({sourceCount})</span>}</button>)}
    </nav>
  )
}
