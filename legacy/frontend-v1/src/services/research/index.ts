import type { AuthorityKind, CorpusStats, LegalAnswer, ResearchResult } from '../../types'
import { request } from '../api/client'

export interface CorpusFilters {
  kinds?: AuthorityKind[]
  court?: string
  jurisdiction?: string
  yearFrom?: number
  yearTo?: number
  caseType?: string
  topic?: string
  citation?: string
  article?: string
  statute?: string
  source?: string
}

const clean = (f: CorpusFilters) => ({
  kinds: f.kinds ?? [], court: f.court || null, jurisdiction: f.jurisdiction || null, yearFrom: f.yearFrom || null, yearTo: f.yearTo || null,
  caseType: f.caseType || null, topic: f.topic || null, citation: f.citation || null, article: f.article || null,
  statute: f.statute || null, source: f.source || null,
})

export const research = (query: string, f: CorpusFilters = {}, limit = 8) =>
  request<ResearchResult>('/research', { body: { query, limit, ...clean(f) } })

/** Grounded answer: every claim links to evidence → document → original source, or the answer says it cannot be supported. */
export const askCorpus = (question: string, f: CorpusFilters = {}) =>
  request<LegalAnswer>('/research/answer', { body: { question, ...clean(f) } })

export const corpusStats = () => request<CorpusStats>('/research/corpus')

export const KIND_LABEL: Record<AuthorityKind, string> = {
  constitution_article: 'Constitution · Article', statute_section: 'Statute · Section', rule: 'Rule', regulation: 'Regulation', judgment: 'Judgment',
}
