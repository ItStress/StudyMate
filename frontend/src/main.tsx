import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

const root = document.getElementById('root')

if (!root) {
  throw new Error('Elemento root non trovato')
}

createRoot(root).render(
  <StrictMode>
    <main>
      <h1>StudyMate</h1>
    </main>
  </StrictMode>,
)
