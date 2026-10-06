type IconName = 'book' | 'upload' | 'file' | 'chat' | 'arrow' | 'external' | 'search' | 'trash' | 'plus'

const paths: Record<IconName, string> = {
  book: 'M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Zm0 0v15',
  upload: 'M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5',
  file: 'M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8m-8 4h5',
  chat: 'M21 11a9 9 0 0 1-9 9H3l2-5a9 9 0 1 1 16-4ZM8 10h8m-8 4h5',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  external: 'M14 3h7v7m0-7L10 14M10 3H3v18h18v-7',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm5-2 5 5',
  trash: 'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7',
  plus: 'M12 5v14M5 12h14',
}

export function Icon({ name, className = 'size-5' }: { name: IconName; className?: string }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
