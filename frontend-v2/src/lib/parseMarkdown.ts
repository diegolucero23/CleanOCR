import type { PageData } from '@/types'

// Splits the stitcher output (10-dash separator + **Page:** N header) into PageData[].
// Reference: frontend/src/components/DiffViewer.tsx::parseMarkdownByPage
export function parseMarkdownToPages(md: string): PageData[] {
  if (!md.trim()) return []

  // Strip YAML frontmatter if present
  let content = md
  if (content.startsWith('---')) {
    const end = content.indexOf('\n---', 3)
    if (end !== -1) content = content.slice(end + 4)
  }

  const chunks = content.split(/\n-{10,}\s*\n/)
  const pages: PageData[] = []

  for (const chunk of chunks) {
    if (!chunk.trim()) continue

    const pageMatch = chunk.match(/\*\*Page:\*\*\s*(\d+)/) ?? chunk.match(/Page:\s*(\d+)/)
    if (!pageMatch) continue

    const pageNumber = parseInt(pageMatch[1], 10)

    const volMatch = chunk.match(/\*\*Volume:\*\*\s*(\S+)/)
    const issMatch = chunk.match(/\*\*Issue:\*\*\s*(\S+)/)
    const dateMatch = chunk.match(/\*\*Date:\*\*\s*([^\n|*]+)/)

    pages.push({
      pageNumber,
      markdownContent: chunk.trim(),
      volume: volMatch?.[1],
      issue: issMatch?.[1],
      date: dateMatch?.[1]?.trim(),
    })
  }

  return pages.sort((a, b) => a.pageNumber - b.pageNumber)
}
