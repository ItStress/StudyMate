import { useEffect, useRef, useState } from 'react'
import { deleteDocument, listDocuments, retryPreparation, uploadDocument } from './api'
import type { PdfDocument } from './types'

const maxPdfBytes = 25 * 1024 * 1024
const pdfSignature = [37, 80, 68, 70, 45]

async function validateFile(file: File): Promise<string | null> {
  if (!file.name.toLowerCase().endsWith('.pdf') ||
      !['', 'application/pdf', 'application/octet-stream'].includes(file.type)) {
    return 'Only PDF files are supported.'
  }
  if (file.size === 0) return 'The PDF is empty.'
  if (file.size > maxPdfBytes) return 'The PDF exceeds 25 MiB.'

  const header = new Uint8Array(await file.slice(0, 5).arrayBuffer())
  if (!pdfSignature.every((byte, index) => header[index] === byte)) {
    return 'The file is not a PDF.'
  }
  return null
}

export function usePdfDocuments() {
  const [documents, setDocuments] = useState<PdfDocument[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const uploading = useRef(false)
  const [retryingId, setRetryingId] = useState<string | null>(null)
  // Reject list responses that started before a local upload, retry or deletion.
  const revision = useRef(0)
  const hasPending = documents.some(({ preparation }) =>
    preparation.status === 'queued' || preparation.status === 'processing')

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
    if (!hasPending || isLoading) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function refresh() {
      const startedRevision = revision.current
      try {
        const updated = await listDocuments(controller.signal)
        if (!controller.signal.aborted && startedRevision === revision.current) setDocuments(updated)
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : 'Could not refresh preparation status.')
        }
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 2000)
      }
    }
    timer = setTimeout(refresh, 2000)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [hasPending, isLoading])

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

  async function retryDocument(id: string) {
    if (retryingId) return
    setRetryingId(id)
    revision.current += 1
    setError('')
    try {
      const updated = await retryPreparation(id)
      revision.current += 1
      setDocuments((current) => current.map((document) => document.id === id ? updated : document))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not retry preparation.')
    } finally {
      setRetryingId(null)
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
    retryingId,
    retryDocument,
    addFiles,
    selectDocument: setSelectedId,
    removeDocument,
  }
}
