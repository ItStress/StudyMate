import { useEffect, useRef, useState } from 'react'
import { deleteDocument, listDocuments, uploadDocument } from './api'
import type { PdfDocument } from './types'
import { validateFile } from './validation'

export function usePdfDocuments() {
  const [documents, setDocuments] = useState<PdfDocument[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const uploading = useRef(false)
  // Reject list responses that started before a local upload or deletion.
  const revision = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    listDocuments(controller.signal)
      .then(setDocuments)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : 'Could not load PDFs.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (isLoading) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function refresh() {
      const startedRevision = revision.current
      try {
        const updated = await listDocuments(controller.signal)
        if (!controller.signal.aborted && startedRevision === revision.current) setDocuments(updated)
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : 'Could not refresh PDF availability.')
        }
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 3000)
      }
    }
    timer = setTimeout(refresh, 2000)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [isLoading])

  async function addFiles(fileList: FileList | null) {
    if (uploading.current || isLoading) return
    const files = Array.from(fileList ?? [])
    if (files.length === 0) return

    uploading.current = true
    revision.current += 1
    setIsUploading(true)
    setError('')
    const failures: string[] = []

    for (const file of files) {
      try {
        const validationError = await validateFile(file)
        if (validationError) {
          failures.push(`${file.name}: ${validationError}`)
          continue
        }
        const document = await uploadDocument(file)
        revision.current += 1
        setDocuments((current) => [document, ...current])
        setSelectedId(document.id)
      } catch (cause) {
        failures.push(`${file.name}: ${cause instanceof Error ? cause.message : 'Upload failed.'}`)
      }
    }

    setError(failures.join(' '))
    uploading.current = false
    setIsUploading(false)
  }

  async function removeDocument(id: string) {
    if (deletingId) return
    setDeletingId(id)
    revision.current += 1
    setError('')
    try {
      await deleteDocument(id)
      revision.current += 1
      setDocuments((current) => current.filter((document) => document.id !== id))
      setSelectedId((current) => current === id ? null : current)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not remove PDF.')
    } finally {
      setDeletingId(null)
    }
  }

  return {
    documents,
    selectedId,
    selectedDocument: documents.find((document) => document.id === selectedId),
    error,
    isLoading,
    isUploading,
    deletingId,
    addFiles,
    selectDocument: setSelectedId,
    removeDocument,
  }
}
