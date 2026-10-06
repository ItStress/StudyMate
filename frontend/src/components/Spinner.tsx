export function Spinner({ label, className = 'size-4' }: { label: string; className?: string }) {
  return <span role="status" className="inline-flex items-center text-accent">
    <svg className={`${className} motion-safe:animate-spin`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" opacity="0.2" />
      <path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
    <span className="sr-only">{label}</span>
  </span>
}
