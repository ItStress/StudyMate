import { useEffect, useRef, useState } from 'react'
import type { PdfDocument } from './types'

export function usePdfDocuments() {
  const [documents, setDocuments] = useState<PdfDocument[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const nextId = useRef(0)
  const objectUrls = useRef(new Set<string>())

  useEffect(() => {
    const urls = objectUrls.current

    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url))
      urls.clear()
    }
  }, [])

  function addFiles(fileList: FileList | null) {
    const files = Array.from(fileList ?? [])
    const pdfs = files.filter(
      (file) => file.type === 'application/pdf' || (file.type === '' && /\.pdf$/i.test(file.name)),
    )
    setError(files.length > pdfs.length ? 'Only PDF files can be added.' : '')

    if (pdfs.length === 0) return

    const added = pdfs.map((file) => {
      const url = URL.createObjectURL(file)
      objectUrls.current.add(url)

      return { id: nextId.current++, name: file.name, url }
    })

    setDocuments((current) => [...current, ...added])
    setSelectedId(added[added.length - 1].id)
  }

  function removeDocument(id: number) {
    const document = documents.find((item) => item.id === id)
    if (!document) return

    setDocuments((current) => current.filter((item) => item.id !== id))
    setSelectedId((current) => current === id ? null : current)
    objectUrls.current.delete(document.url)
    URL.revokeObjectURL(document.url)
  }

  return {
    documents,
    selectedId,
    selectedDocument: documents.find((document) => document.id === selectedId),
    error,
    addFiles,
    selectDocument: setSelectedId,
    removeDocument,
  }
}
