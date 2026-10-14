import type { PracticeArea } from '../types'

export const ALL_AREAS: PracticeArea[] = ['Criminal', 'Family', 'Property', 'Corporate', 'Consumer', 'Cyber', 'Labour', 'Constitutional']

export const inr = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`

export const initials = (name: string) => name.replace(/^(Adv\.|Justice)\s+/, '').split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase()
