'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { AlertCircle, ArrowRight, Building2, LoaderCircle } from 'lucide-react'
import { login, register } from '@/services/auth.service'
import { setSession } from '@/lib/mock-auth'

export default function OrganizationSetupPage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [orgName, setOrgName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleContinue(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await register(name, email, password, orgName)
      const sessionResponse = await login(email, password)
      setSession({
        user: sessionResponse.user,
        organization: response.organization,
        access_token: sessionResponse.access_token,
      })
      router.push('/setup/connector')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Workspace setup failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        width: '100%',
        maxWidth: 480,
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
        padding: '40px 32px',
        background: 'var(--color-surface)',
        boxShadow: 'var(--shadow-md)',
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          borderRadius: 4,
          padding: '4px 10px',
          fontSize: 12,
          fontWeight: 'var(--font-weight-semibold)',
          background: 'var(--color-accent-light)',
          color: 'var(--color-accent)',
          marginBottom: 16,
        }}
      >
        <Building2 style={{ width: 14, height: 14 }} />
        Step 1 of 2
      </div>

      <h1 style={{ fontSize: 18, fontWeight: 'var(--font-weight-bold)', marginBottom: 4 }}>
        Create your organization
      </h1>
      <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 28 }}>
        Create an account and its first workspace. You can import demo data next.
      </p>

      {error && (
        <div className="error-alert" role="alert">
          <AlertCircle />
          {error}
        </div>
      )}

      <form onSubmit={handleContinue}>
        <div className="form-group">
          <label htmlFor="name" className="form-label">Your name</label>
          <input id="name" type="text" value={name} onChange={(e) => setName(e.target.value)} required className="form-input" autoComplete="name" />
        </div>

        <div className="form-group">
          <label htmlFor="email" className="form-label">Work email</label>
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="form-input" autoComplete="email" />
        </div>

        <div className="form-group">
          <label htmlFor="password" className="form-label">Password</label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} className="form-input" autoComplete="new-password" />
        </div>

        <div className="form-group">
          <label htmlFor="orgName" className="form-label">Organization name</label>
          <input
            id="orgName"
            type="text"
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            required
            className="form-input"
          />
        </div>

        <button type="submit" disabled={loading} className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', opacity: loading ? 0.65 : 1 }}>
          {loading ? <LoaderCircle className="spin" /> : <ArrowRight />}
          {loading ? 'Creating workspace...' : 'Create workspace'}
        </button>
      </form>

      <p style={{ marginTop: 16, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
        <Link href="/login" style={{ fontWeight: 'var(--font-weight-medium)', color: 'var(--color-accent)' }}>
          Back to Login
        </Link>
      </p>
    </div>
  )
}
