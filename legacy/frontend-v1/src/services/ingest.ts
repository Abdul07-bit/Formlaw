// Client-side pre-checks for uploads (fast feedback only). The server re-validates every file:
// extension, MIME type and actual content, decompression bombs, active PDF content, size.

export const MAX_FILE_BYTES = 15 * 1024 * 1024

const ALLOWED: Record<string, { mimes: string[]; label: string }> = {
  pdf: { mimes: ['application/pdf'], label: 'PDF' },
  docx: { mimes: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'], label: 'DOCX' },
  txt: { mimes: ['text/plain', ''], label: 'TXT' },
  md: { mimes: ['text/markdown', 'text/plain', ''], label: 'MD' },
  csv: { mimes: ['text/csv', 'application/vnd.ms-excel', 'text/plain', ''], label: 'CSV' },
  png: { mimes: ['image/png'], label: 'PNG' },
  jpg: { mimes: ['image/jpeg'], label: 'JPG' },
  jpeg: { mimes: ['image/jpeg'], label: 'JPEG' },
}

export const ACCEPT_ATTR = Object.keys(ALLOWED).map((e) => `.${e}`).join(',')
export const ALLOWED_LABELS = [...new Set(Object.values(ALLOWED).map((a) => a.label))]

export function sanitizeFilename(name: string): string {
  const base = name.split(/[\/]/).pop() ?? 'document'
  const cleaned = base.normalize('NFKD').replace(/[^\w.\- ]+/g, '').replace(/\.{2,}/g, '.').replace(/^\.+/, '').trim().slice(0, 120)
  return cleaned || 'document'
}

export type ValidationResult = { ok: true; ext: string } | { ok: false; reason: string }

export function validateFile(file: File): ValidationResult {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  const rule = ALLOWED[ext]
  if (!rule) return { ok: false, reason: `.${ext || '?'} files are not supported` }
  if (file.size === 0) return { ok: false, reason: 'File is empty' }
  if (file.size > MAX_FILE_BYTES) return { ok: false, reason: 'File exceeds 15 MB limit' }
  if (!rule.mimes.includes(file.type)) return { ok: false, reason: 'File type does not match its extension' }
  return { ok: true, ext }
}

export const formatBytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`
