'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, LineChart, AlertTriangle } from 'lucide-react'
import { useCampaignDetails } from '@/hooks/useCampaigns'
import { useAnomalies } from '@/hooks/useAnomalies'

export default function CampaignDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { data: details, isLoading } = useCampaignDetails(id)
  const { data: allAnomalies } = useAnomalies()
  const anomalies = allAnomalies?.filter((a) => a.campaign_id === id) ?? []

  if (isLoading) {
    return (
      <div style={{ padding: '48px 0', textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
        Loading campaign details...
      </div>
    )
  }

  if (!details) {
    return (
      <div style={{ padding: '48px 0', textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
        Campaign not found.
      </div>
    )
  }

  const campaign = details.campaign

  const kpis = [
    { label: 'Spend', value: `${campaign.spend.toLocaleString()} EGP` },
    { label: 'Clicks', value: campaign.clicks.toLocaleString() },
    { label: 'Conversions', value: campaign.conversions.toLocaleString() },
    { label: 'CPA', value: `${campaign.cpa.toFixed(1)} EGP`, danger: campaign.cpa > 150 },
    { label: 'ROAS', value: `${campaign.roas.toFixed(1)}x`, success: campaign.roas >= 4 },
  ]

  return (
    <>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <Link href="/campaigns">
          <ArrowLeft />
          Campaigns
        </Link>
        <span>/</span>
        <span>{campaign.name}</span>
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 14, marginBottom: 24 }}>
        {kpis.map((k) => (
          <div key={k.label} className="kpi-card">
            <div className="kpi-label">{k.label}</div>
            <div
              className="kpi-value"
              style={{
                color: k.danger ? 'var(--color-error)' : k.success ? 'var(--color-success)' : undefined,
              }}
            >
              {k.value}
            </div>
          </div>
        ))}
      </div>

      {/* Performance chart placeholder */}
      <div className="card">
        <div className="card-header">
          <LineChart />
          Performance Trend
        </div>
        <div className="chart-placeholder">
          <LineChart />
          Recharts line chart — CPA, ROAS, CTR over time
        </div>
      </div>

      {/* Anomalies for this campaign */}
      {anomalies.length > 0 && (
        <div className="card">
          <div className="card-header">
            <AlertTriangle />
            Anomalies
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {anomalies.map((a) => (
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
                <div>
                  <div style={{ fontSize: 13, fontWeight: 'var(--font-weight-semibold)' }}>
                    {a.metric_name} anomaly ({a.direction})
                  </div>
                  <div style={{ marginTop: 2, fontSize: 12, lineHeight: 1.4, color: 'var(--color-text-muted)' }}>
                    Score: {a.anomaly_score.toFixed(2)} &middot; Severity: {a.severity}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
