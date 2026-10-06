type MarkdownNode = {
  type: string
  value?: string
  url?: string
  children?: MarkdownNode[]
}

// Convert verified references to links before rendering, keeping Markdown structure intact.
export function remarkCitations({ numbers }: { numbers: number[] }) {
  const known = new Set(numbers)
  return (tree: MarkdownNode) => {
    function visit(node: MarkdownNode) {
      if (!node.children || ['link', 'image', 'code', 'inlineCode'].includes(node.type)) return
      node.children = node.children.flatMap((child) => {
        if (child.type !== 'text' || !child.value) {
          visit(child)
          return [child]
        }
        return child.value.split(/(\[\d+\])/g).filter(Boolean).map((part): MarkdownNode => {
          const match = /^\[(\d+)\]$/.exec(part)
          return match && known.has(Number(match[1]))
            ? { type: 'link', url: `#studymate-citation-${match[1]}`, children: [{ type: 'text', value: part }] }
            : { type: 'text', value: part }
        })
      })
    }
    visit(tree)
  }
}
