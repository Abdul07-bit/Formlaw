import type { CaseDocument } from '../types'
import { uid } from './store'

// Document ingestion: validate → sanitise → extract text → structure.
// Text formats are extracted live in the browser. PDF/DOCX/XLSX/images are accepted and
// queued for server-side extraction/OCR (backend contract: POST /api/documents).

export const MAX_FILE_BYTES = 15 * 1024 * 1024

const ALLOWED: Record<string, { mimes: string[]; live: boolean; label: string }> = {
  pdf: { mimes: ['application/pdf'], live: false, label: 'PDF' },
  docx: { mimes: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'], live: false, label: 'DOCX' },
  txt: { mimes: ['text/plain', ''], live: true, label: 'TXT' },
  md: { mimes: ['text/markdown', 'text/plain', ''], live: true, label: 'MD' },
  csv: { mimes: ['text/csv', 'application/vnd.ms-excel', 'text/plain', ''], live: true, label: 'CSV' },
  xlsx: { mimes: ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'], live: false, label: 'XLSX' },
  png: { mimes: ['image/png'], live: false, label: 'PNG' },
  jpg: { mimes: ['image/jpeg'], live: false, label: 'JPG' },
  jpeg: { mimes: ['image/jpeg'], live: false, label: 'JPEG' },
}

export const ACCEPT_ATTR = Object.keys(ALLOWED).map((e) => `.${e}`).join(',')
export const ALLOWED_LABELS = [...new Set(Object.values(ALLOWED).map((a) => a.label))]

export function sanitizeFilename(name: string): string {
  const base = name.split(/[\\/]/).pop() ?? 'document'
  const cleaned = base
    .normalize('NFKD')
    .replace(/[^\w.\- ]+/g, '')
    .replace(/\.{2,}/g, '.')
    .replace(/^\.+/, '')
    .trim()
    .slice(0, 120)
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

export async function ingestFile(file: File): Promise<CaseDocument> {
  const v = validateFile(file)
  if (!v.ok) throw new Error(v.reason)
  const rule = ALLOWED[v.ext]
  let text = ''
  if (rule.live) {
    // Read as text only — uploaded content is never executed or rendered as HTML.
    text = (await file.text()).replace(/\u0000/g, '').slice(0, 200_000)
  }
  const pages = text ? Math.max(1, (text.match(/\[\[PAGE \d+\]\]/g) ?? []).length || Math.ceil(text.length / 1800)) : undefined
  return {
    id: uid('DOC'),
    name: sanitizeFilename(file.name),
    type: file.type || 'text/plain',
    size: file.size,
    text,
    extraction: rule.live ? 'live' : 'backend',
    pages,
  }
}

export interface Chunk { docId: string; docName: string; page: number; sentence: string }

// Split documents into page-aware sentence chunks for retrieval.
export function chunkDocuments(docs: CaseDocument[]): Chunk[] {
  const out: Chunk[] = []
  for (const d of docs) {
    if (!d.text) continue
    let page = 1
    for (const line of d.text.split(/\r?\n/)) {
      const m = line.match(/\[\[PAGE (\d+)\]\]/)
      if (m) { page = Number(m[1]); continue }
      const parts = line.split(/(?<=[.!?])\s+(?=[A-Z])/)
      for (const p of parts) {
        const s = p.trim()
        if (s.length > 3) out.push({ docId: d.id, docName: d.name, page, sentence: s })
      }
    }
  }
  return out
}

export const formatBytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`
