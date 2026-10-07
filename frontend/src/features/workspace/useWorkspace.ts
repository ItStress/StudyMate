import { useState } from 'react'
import { usePdfDocuments } from '../documents/usePdfDocuments'
import type { Citation } from '../chat/types'
import type { WorkspaceView } from './types'

export function useWorkspace() {
  const documentState = usePdfDocuments()
  const { documents, selectDocument } = documentState
  const [sourceIds, setSourceIds] = useState<string[]>([])
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>('reading')
  const [preview, setPreview] = useState({ id: '', page: 1, navigation: 0 })
  const sources = documents.filter((doc) => sourceIds.includes(doc.id)).sort((a, b) => a.id.localeCompare(b.id))

  function openDocument(id: string, page = 1) {
    selectDocument(id)
    setPreview((current) => ({ id, page, navigation: current.navigation + 1 }))
  }

  function openCitation(citation: Citation) {
    openDocument(citation.document_id, citation.page_number)
    setWorkspaceView('reading')
  }

  function toggleSource(id: string) {
    setSourceIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])
  }

  return { ...documentState, sources, workspaceView, setWorkspaceView, preview, openDocument, openCitation, toggleSource }
}
