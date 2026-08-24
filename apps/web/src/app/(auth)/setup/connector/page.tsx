'use client'

import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  Plug,
  ArrowRight,
  Search,
  Share2,
  BarChart3,
  FileSpreadsheet,
  CheckCircle2,
  Plus,
  Upload,
  UploadCloud,
} from 'lucide-react'
import { setSession, DEMO_SESSION } from '@/lib/mock-auth'

const CONNECTORS = [
  {
    name: 'Google Ads',
    status: 'Connected',
    connected: true,
    icon: Search,
    iconBg: 'var(--color-info-light)',
    iconColor: 'var(--color-info)',
  },
  {
    name: 'Meta Ads',
    status: 'Not connected',
    connected: false,
    icon: Share2,
    iconBg: 'var(--color-accent-light)',
    iconColor: 'var(--color-accent)',
  },
  {
    name: 'Google Analytics 4',
    status: 'Not connected',
    connected: false,
    icon: BarChart3,
    iconBg: 'var(--color-warning-light)',
    iconColor: 'var(--color-warning)',
  },
  {
    name: 'CSV Upload',
    status: 'Demo data',
    connected: false,
    icon: FileSpreadsheet,
    iconBg: 'var(--color-surface-raised)',
    iconColor: 'var(--color-text-muted)',
  },
] as const

export default function ConnectorSetupPage() {
  const router = useRouter()

  function handleContinue() {
    setSession(DEMO_SESSION)
    router.push('/dashboard')
  }

  return (
    <div
      style={{
        width: '100%',
        maxWidth: 540,
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
        <Plug style={{ width: 14, height: 14 }} />
        Step 2 of 2
      </div>

      <h1 style={{ fontSize: 18, fontWeight: 'var(--font-weight-bold)', marginBottom: 4 }}>
        Connect your ad platforms
      </h1>
      <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 28 }}>
        Link at least one data source so Sawakli can start analyzing your campaigns.
      </p>

      {/* Connector grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 24 }}>
        {CONNECTORS.map((c) => (
          <div
            key={c.name}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              borderRadius: 'var(--radius-md)',
              border: `1px solid ${c.connected ? 'var(--color-success-border)' : 'var(--color-border)'}`,
              padding: 14,
              cursor: 'pointer',
              background: c.connected ? 'var(--color-success-light)' : undefined,
              transition: 'border-color var(--transition), background var(--transition)',
            }}
          >
            <div
              style={{
                display: 'flex',
                width: 36,
                height: 36,
                flexShrink: 0,
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 8,
                background: c.iconBg,
                color: c.iconColor,
              }}
            >
              <c.icon style={{ width: 18, height: 18 }} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 'var(--font-weight-semibold)' }}>{c.name}</div>
              <div
                style={{
                  fontSize: 12,
                  color: c.connected ? 'var(--color-success)' : 'var(--color-text-muted)',
                  fontWeight: c.connected ? 500 : 400,
                }}
              >
                {c.status}
              </div>
            </div>
            <div style={{ flexShrink: 0, color: c.connected ? 'var(--color-success)' : 'var(--color-text-faint)' }}>
              {c.connected ? (
                <CheckCircle2 style={{ width: 16, height: 16 }} />
              ) : c.name === 'CSV Upload' ? (
                <Upload style={{ width: 16, height: 16 }} />
              ) : (
                <Plus style={{ width: 16, height: 16 }} />
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Or divider */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, fontSize: 12, fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-faint)' }}>
        <span style={{ height: 1, flex: 1, background: 'var(--color-border)' }} />
        or upload demo data
        <span style={{ height: 1, flex: 1, background: 'var(--color-border)' }} />
      </div>

      {/* Upload zone */}
      <div
        style={{
          marginBottom: 24,
          cursor: 'pointer',
          borderRadius: 'var(--radius-md)',
          border: '2px dashed var(--color-border)',
          padding: 24,
          textAlign: 'center',
          transition: 'border-color var(--transition)',
        }}
      >
        <UploadCloud style={{ width: 24, height: 24, margin: '0 auto 8px', color: 'var(--color-text-faint)' }} />
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Drag and drop a CSV file, or{' '}
          <strong style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-accent)' }}>browse</strong>
        </p>
      </div>

      <button onClick={handleContinue} className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
        <ArrowRight style={{ width: 16, height: 16 }} />
        Continue to Dashboard
      </button>

      <p style={{ marginTop: 16, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
        <Link href="/setup/organization" style={{ fontWeight: 'var(--font-weight-medium)', color: 'var(--color-accent)' }}>
          Back to Organization Setup
        </Link>
      </p>
    </div>
  )
}
