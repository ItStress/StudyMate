const maxPdfBytes = 25 * 1024 * 1024
const pdfSignature = [37, 80, 68, 70, 45]

export async function validateFile(file: File): Promise<string | null> {
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
