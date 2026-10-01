import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import './style.css'

type PdfDocument = {
  id: number
  name: string
  url: string
}

export default function App() {
  const [documents, setDocuments] = useState<PdfDocument[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const nextId = useRef(0)
  const objectUrls = useRef(new Set<string>())

  useEffect(() => {
    const urls = objectUrls.current

    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url))
      urls.clear()
    }
  }, [])

  function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.currentTarget.files ?? [])
    event.currentTarget.value = ''

    const pdfs = files.filter(
      (file) => file.type === 'application/pdf' || (file.type === '' && /\.pdf$/i.test(file.name)),
    )
    const rejectedCount = files.length - pdfs.length
    setError(rejectedCount > 0 ? 'Only PDF files can be added.' : '')

    if (pdfs.length === 0) return

    const added = pdfs.map((file) => {
      const url = URL.createObjectURL(file)
      objectUrls.current.add(url)

      return { id: nextId.current++, name: file.name, url }
    })

    setDocuments((current) => [...current, ...added])
    setSelectedId(added[added.length - 1].id)
  }

  const selectedDocument = documents.find((document) => document.id === selectedId)

  return (
    <main className="app-shell">
      <header className="page-header">
        <span className="eyebrow">Your study space</span>
        <h1>StudyMate</h1>
        <p>Add PDFs to view them here. Your files stay in this browser session.</p>
      </header>

      <div className="workspace">
        <section className="documents-panel" aria-labelledby="documents-heading">
          <div className="panel-heading">
            <div>
              <h2 id="documents-heading">Documents</h2>
              <p>{documents.length} {documents.length === 1 ? 'PDF' : 'PDFs'} added</p>
            </div>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,application/pdf"
              multiple
              onChange={handleFileSelection}
              className="file-input"
              aria-label="Choose PDF files"
            />
            <button type="button" className="upload-button" onClick={() => fileInput.current?.click()}>
              Add PDFs
            </button>
          </div>

          {error && <p className="error-message" role="alert">{error}</p>}

          {documents.length === 0 ? (
            <div className="empty-documents">
              <div className="document-icon" aria-hidden="true">PDF</div>
              <p>No PDFs added yet</p>
              <span>Choose one or more files to get started.</span>
            </div>
          ) : (
            <ul className="document-list">
              {documents.map((document) => (
                <li key={document.id}>
                  <button
                    type="button"
                    className={`document-button${document.id === selectedId ? ' selected' : ''}`}
                    aria-pressed={document.id === selectedId}
                    onClick={() => setSelectedId(document.id)}
                  >
                    <span className="document-mark" aria-hidden="true">PDF</span>
                    <span className="document-name">{document.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="preview-panel" aria-labelledby="preview-heading">
          <div className="preview-heading">
            <div>
              <span className="eyebrow">Preview</span>
              <h2 id="preview-heading">{selectedDocument?.name ?? 'Select a PDF'}</h2>
            </div>
            {selectedDocument && (
              <a href={selectedDocument.url} target="_blank" rel="noopener noreferrer">
                Open PDF
              </a>
            )}
          </div>
          {selectedDocument ? (
            <iframe
              className="pdf-preview"
              src={selectedDocument.url}
              title={`Preview of ${selectedDocument.name}`}
            />
          ) : (
            <div className="empty-preview">Your selected PDF will appear here.</div>
          )}
        </section>
      </div>
    </main>
  )
}

