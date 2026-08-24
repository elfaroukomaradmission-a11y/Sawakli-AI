'use client'

import {
  Wallet,
  MousePointerClick,
  ShoppingCart,
  Target,
  TrendingUp,
  TrendingDown,
  LineChart,
  ArrowRight,
  AlertTriangle,
  Lightbulb,
} from 'lucide-react'
import Link from 'next/link'
import { useAnomalies } from '@/hooks/useAnomalies'
import { useRecommendations } from '@/hooks/useRecommendations'
import { getSession } from '@/lib/mock-auth'

const KPI_DATA = [
  {
    label: 'Total Spend',
    value: '42,500 EGP',
    delta: '+12% vs last month',
    positive: true,
    icon: Wallet,
    status: 'success' as const,
  },
  {
    label: 'Total Clicks',
    value: '8,240',
    delta: '+8% vs last month',
    positive: true,
    icon: MousePointerClick,
    status: null,
  },
  {
    label: 'Conversions',
    value: '312',
    delta: '-5% vs last month',
    positive: false,
    icon: ShoppingCart,
    status: 'warning' as const,
  },
  {
    label: 'Avg CPA',
    value: '136.2 EGP',
    delta: '+18% vs last month',
    positive: false,
    icon: Target,
    status: 'error' as const,
  },
]

function kpiStatusStyle(status: 'success' | 'warning' | 'error' | null): React.CSSProperties {
  if (!status) return {}
  const map = {
    success: { borderColor: 'rgba(24,145,94,0.15)', boxShadow: 'var(--shadow-status-success)' },
    warning: { borderColor: 'rgba(200,138,4,0.18)', boxShadow: 'var(--shadow-status-warning)' },
    error: { borderColor: 'rgba(217,54,68,0.2)', boxShadow: 'var(--shadow-status-error)' },
  }
  return map[status]
}

export default function DashboardPage() {
  const session = getSession()
  const orgId = session?.organization.id ?? ''
  const { data: anomalies } = useAnomalies()
  const { data: recommendations } = useRecommendations(orgId)

  const pendingRecs = recommendations?.filter((r) => r.status === 'pending') ?? []

  return (
    <>
      {/* KPI Row */}
      <div className="kpi-grid">
        {KPI_DATA.map((kpi) => (
          <div
            key={kpi.label}
            className="kpi-card"
            style={kpiStatusStyle(kpi.status)}
          >
            <div className="kpi-label">
              <kpi.icon style={{ width: 13, height: 13, display: 'inline', verticalAlign: '-2px', marginRight: 5 }} />
              {kpi.label}
            </div>
            <div className="kpi-value">{kpi.value}</div>
            <div
              className="kpi-change"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                color: kpi.positive ? 'var(--color-success)' : 'var(--color-error)',
              }}
            >
              {kpi.positive ? (
                <TrendingUp style={{ width: 12, height: 12 }} />
              ) : (
                <TrendingDown style={{ width: 12, height: 12 }} />
              )}
              {kpi.delta}
            </div>
          </div>
        ))}
      </div>

      {/* Performance Overview Chart Placeholder */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
          <div className="card-header" style={{ marginBottom: 0 }}>
            <LineChart />
            Performance Overview
          </div>
          <Link
            href="/campaigns"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-accent)' }}
          >
            View Campaigns <ArrowRight style={{ width: 12, height: 12 }} />
          </Link>
        </div>
        <div className="chart-placeholder">
          <LineChart />
          Recharts area chart — spend, clicks, conversions over 30 days
        </div>
      </div>

      {/* Two-column: Anomalies + Recommendations */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        {/* Active Anomalies */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <AlertTriangle />
            Active Anomalies
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {anomalies?.map((a) => (
              <div
                key={a.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border)',
                  padding: 12,
                  background: a.severity === 'high' ? 'var(--color-error-light)' : 'var(--color-warning-light)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    width: 32,
                    height: 32,
                    flexShrink: 0,
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: 8,
                    background: a.severity === 'high' ? 'rgba(217,54,68,0.12)' : 'rgba(200,138,4,0.12)',
                    color: a.severity === 'high' ? 'var(--color-error)' : 'var(--color-warning)',
                  }}
                >
                  <AlertTriangle style={{ width: 16, height: 16 }} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 'var(--font-weight-semibold)', marginBottom: 2 }}>{a.title}</div>
                  <div style={{ fontSize: 12, lineHeight: 1.4, color: 'var(--color-text-muted)' }}>
                    {a.description}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 11, color: 'var(--color-text-faint)' }}>
                    {a.detected_at}
                  </div>
                </div>
              </div>
            ))}
            {(!anomalies || anomalies.length === 0) && (
              <p style={{ padding: '16px 0', textAlign: 'center', fontSize: 12, color: 'var(--color-text-muted)' }}>
                No active anomalies detected.
              </p>
            )}
          </div>
        </div>

        {/* Pending Recommendations */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
            <div className="card-header" style={{ marginBottom: 0 }}>
              <Lightbulb />
              Pending Recommendations
            </div>
            <Link
              href="/recommendations"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-accent)' }}
            >
              View All <ArrowRight style={{ width: 12, height: 12 }} />
            </Link>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {pendingRecs.map((r) => (
              <Link
                key={r.id}
                href={`/recommendations/${r.id}`}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border)',
                  padding: 12,
                  color: 'inherit',
                  transition: 'border-color var(--transition)',
                }}
              >
                <span
                  style={{
                    marginTop: 5,
                    display: 'block',
                    width: 8,
                    height: 8,
                    flexShrink: 0,
                    borderRadius: '50%',
                    background:
                      r.risk === 'high'
                        ? 'var(--color-error)'
                        : r.risk === 'medium'
                          ? 'var(--color-warning)'
                          : 'var(--color-success)',
                  }}
                />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 'var(--font-weight-semibold)' }}>{r.title}</div>
                  <div style={{ marginTop: 2, fontSize: 12, color: 'var(--color-text-muted)' }}>
                    {r.campaign_name} · {r.confidence}% confidence
                  </div>
                </div>
              </Link>
            ))}
            {pendingRecs.length === 0 && (
              <p style={{ padding: '16px 0', textAlign: 'center', fontSize: 12, color: 'var(--color-text-muted)' }}>
                No pending recommendations.
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
