'use client'

import Link from 'next/link'
import { useCampaigns } from '@/hooks/useCampaigns'
import { getSession } from '@/lib/mock-auth'
import type { Campaign } from '@/types'

function platformBadge(platform: string) {
  const styles =
    platform === 'Google Ads'
      ? { background: 'var(--color-badge-google-bg)', color: 'var(--color-badge-google-text)' }
      : { background: 'var(--color-accent-light)', color: 'var(--color-accent)' }
  const label = platform === 'Google Ads' ? 'Google' : 'Meta'
  return (
    <span className="badge" style={styles}>
      {label}
    </span>
  )
}

function statusBadge(status: string) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    active: { bg: 'var(--color-success-light)', color: 'var(--color-success)', label: 'Active' },
    paused: { bg: 'var(--color-warning-light)', color: 'var(--color-warning)', label: 'Paused' },
    ended: { bg: 'var(--color-surface-raised)', color: 'var(--color-text-muted)', label: 'Ended' },
  }
  const s = map[status] ?? map.ended
  return (
    <span className="badge" style={{ background: s.bg, color: s.color }}>
      {s.label}
    </span>
  )
}

function healthBadge(health: string) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    strong: { bg: 'var(--color-success-light)', color: 'var(--color-success)', label: 'Strong' },
    average: { bg: 'var(--color-warning-light)', color: 'var(--color-warning)', label: 'Average' },
    weak: { bg: 'var(--color-error-light)', color: 'var(--color-error)', label: 'Weak' },
  }
  const h = map[health] ?? map.average
  return (
    <span className="badge" style={{ background: h.bg, color: h.color }}>
      {h.label}
    </span>
  )
}

function formatNum(n: number): string {
  return n.toLocaleString('en-US')
}

export default function CampaignsPage() {
  const session = getSession()
  const { data: campaigns, isLoading } = useCampaigns(session?.organization.id ?? '')

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '0 0 16px' }}>
        <h2 style={{ fontSize: 14, fontWeight: 'var(--font-weight-bold)' }}>All Campaigns</h2>
      </div>

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr style={{ background: 'var(--color-surface-raised)' }}>
              {['Campaign', 'Platform', 'Status', 'Spend', 'Clicks', 'Conv.', 'CPA', 'ROAS', 'Health'].map((h) => (
                <th key={h} style={{ whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={9} style={{ padding: '32px 14px', textAlign: 'center', fontSize: 12, color: 'var(--color-text-muted)' }}>
                  Loading campaigns...
                </td>
              </tr>
            )}
            {campaigns?.map((c: Campaign) => (
              <tr
                key={c.id}
                style={{
                  background: c.health_status === 'weak' ? 'var(--color-error-light)' : undefined,
                }}
              >
                <td style={{ whiteSpace: 'nowrap', fontWeight: 'var(--font-weight-bold)' }}>
                  <Link href={`/campaigns/${c.id}`} style={{ color: 'inherit' }}>
                    {c.name}
                  </Link>
                </td>
                <td>{platformBadge(c.platform)}</td>
                <td>{statusBadge(c.status)}</td>
                <td>{formatNum(c.spend)} EGP</td>
                <td>{formatNum(c.clicks)}</td>
                <td>{formatNum(c.conversions)}</td>
                <td
                  style={{
                    fontWeight: 'var(--font-weight-semibold)',
                    color: c.cpa > 150 ? 'var(--color-error)' : undefined,
                  }}
                >
                  {c.cpa.toFixed(1)} EGP
                </td>
                <td
                  style={{
                    fontWeight: 'var(--font-weight-semibold)',
                    color: c.roas >= 4 ? 'var(--color-success)' : undefined,
                  }}
                >
                  {c.roas.toFixed(1)}x
                </td>
                <td>{healthBadge(c.health_status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderTop: '1px solid var(--color-border)',
          padding: '10px 14px',
          fontSize: 12,
          color: 'var(--color-text-muted)',
        }}
      >
        <span>Showing {campaigns?.length ?? 0} campaigns</span>
      </div>
    </div>
  )
}
