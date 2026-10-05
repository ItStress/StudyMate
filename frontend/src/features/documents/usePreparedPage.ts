import { useEffect, useState } from 'react'
import { getPreparedPage } from './api'
import type { PageResults } from './types'

export function usePreparedPage(documentId: string, pageNumber: number, publicationId: string | undefined) {
  const [response, setResponse] = useState<{ key: string, data: PageResults } | null>(null)
  const [failure, setFailure] = useState<{ key: string, message: string } | null>(null)
  const [retry, setRetry] = useState(0)
  const key = `${documentId}:${publicationId}:${pageNumber}:${retry}`

  useEffect(() => {
    if (!publicationId) return
    const controller = new AbortController()
    getPreparedPage(documentId, pageNumber, publicationId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResponse({ key, data })
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setFailure({ key, message: cause instanceof Error ? cause.message : 'Could not load this page.' })
        }
      })
    return () => controller.abort()
  }, [documentId, pageNumber, publicationId, key])

  return {
    data: response?.key === key ? response.data : null,
    error: failure?.key === key ? failure.message : '',
    reload: () => setRetry((current) => current + 1),
  }
}
