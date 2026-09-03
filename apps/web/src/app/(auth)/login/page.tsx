'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Brain, LogIn, AlertCircle } from 'lucide-react'
import { login } from '@/services/auth.service'
import { setSession, DEMO_SESSION } from '@/lib/mock-auth'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await login(email, password)
      setSession({
        user: res.user,
        organization: DEMO_SESSION.organization,
        access_token: res.access_token,
      })
      router.push('/dashboard')
    } catch {
      setError('Invalid email or password. Check your credentials and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        width: '100%',
        maxWidth: 400,
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
        padding: '40px 32px',
        background: 'var(--color-surface)',
        boxShadow: 'var(--shadow-md)',
      }}
    >
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
        <div
          style={{
            display: 'flex',
            width: 40,
            height: 40,
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 10,
            background: 'var(--color-accent)',
          }}
        >
          <Brain style={{ width: 22, height: 22, color: '#fff' }} />
        </div>
        <span style={{ fontSize: 20, fontWeight: 'var(--font-weight-bold)', letterSpacing: '-0.01em' }}>
          Sawakli AI
        </span>
      </div>

      <h1 style={{ fontSize: 16, fontWeight: 'var(--font-weight-semibold)', marginBottom: 4 }}>
        Sign in to your account
      </h1>
      <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 24 }}>
        Enter your credentials to access the dashboard.
      </p>

      {error && (
        <div className="error-alert">
          <AlertCircle />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="email" className="form-label">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
            className="form-input"
          />
        </div>

        <div className="form-group">
          <label htmlFor="password" className="form-label">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            required
            className="form-input"
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--color-text-secondary)', cursor: 'pointer' }}>
            <input type="checkbox" style={{ width: 16, height: 16, accentColor: 'var(--color-accent)' }} />
            Remember me
          </label>
          <button
            type="button"
            style={{ fontSize: 13, fontWeight: 'var(--font-weight-medium)', color: 'var(--color-accent)', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            Forgot password?
          </button>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="btn btn-primary"
          style={{
            width: '100%',
            justifyContent: 'center',
            opacity: loading ? 0.6 : 1,
            cursor: loading ? 'default' : 'pointer',
          }}
        >
          <LogIn style={{ width: 16, height: 16 }} />
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>

      <p style={{ marginTop: 24, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
        New to Sawakli?{' '}
        <Link href="/setup/organization" style={{ fontWeight: 'var(--font-weight-medium)', color: 'var(--color-accent)' }}>
          Create an account
        </Link>
      </p>
    </div>
  )
}
