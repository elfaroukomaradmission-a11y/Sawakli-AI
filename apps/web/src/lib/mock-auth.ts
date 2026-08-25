import type { User, Organization } from '@/types'

export type Session = {
  user: User
  organization: Organization
  access_token: string
}

const STORAGE_KEY = 'sawakli-session'
const COOKIE_NAME = 'sawakli-auth'

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value};path=/;samesite=lax`
}

function deleteCookie(name: string) {
  document.cookie = `${name}=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT`
}

export function getSession(): Session | null {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as Session
  } catch {
    return null
  }
}

export function setSession(session: Session): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  setCookie(COOKIE_NAME, '1')
}

export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEY)
  deleteCookie(COOKIE_NAME)
}

export const DEMO_SESSION: Session = {
  user: {
    id: 'demo-001',
    name: 'Ahmed Hassan',
    email: 'demo@fashionbrandx.com',
    role: 'admin',
  },
  organization: {
    id: 'org-001',
    name: 'Fashion Brand X',
    industry: 'Fashion e-commerce',
    currency: 'EGP',
  },
  access_token: 'demo-token-sawakli-2026',
}
