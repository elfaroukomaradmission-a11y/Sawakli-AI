'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, CheckCircle, XCircle, FlaskConical } from 'lucide-react'
import { useRecommendation, useSimulations, useSubmitDecision } from '@/hooks/useRecommendations'

export default function RecommendationDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { data: rec, isLoading } = useRecommendation(id)
  const { data: simulations } = useSimulations(id)
  const submitDecision = useSubmitDecision()

  if (isLoading) {
    return (
      <div style={{ padding: '48px 0', textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
        Loading recommendation...
      </div>
    )
  }

  if (!rec) {
    return (
      <div style={{ padding: '48px 0', textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
        Recommendation not found.
      </div>
    )
  }

  const isPending = rec.status === 'pending'

  return (
    <>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <Link href="/recommendations">
          <ArrowLeft />
          Recommendations
        </Link>
        <span>/</span>
        <span>{rec.title}</span>
      </div>

      {/* Main card */}
      <div className="card">
        {/* Meta */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 14 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-secondary)' }}>
            {rec.campaign_name}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="badge" style={{ background: 'var(--color-accent-light)', color: 'var(--color-accent)' }}>
              {rec.confidence}% confidence
            </span>
            <span
              className="badge"
              style={{
                background: rec.risk === 'high' ? 'var(--color-error-light)' : rec.risk === 'medium' ? 'var(--color-warning-light)' : 'var(--color-success-light)',
                color: rec.risk === 'high' ? 'var(--color-error)' : rec.risk === 'medium' ? 'var(--color-warning)' : 'var(--color-success)',
                textTransform: 'capitalize',
              }}
            >
              {rec.risk} risk
            </span>
          </div>
        </div>

        {/* Title */}
        <h2 style={{ fontSize: 17, fontWeight: 'var(--font-weight-bold)', lineHeight: 1.35, letterSpacing: '-0.01em', marginBottom: 18 }}>
          {rec.title}
        </h2>

        {/* Structured argument */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 18 }}>
          {/* Problem */}
          <div style={{ borderRadius: 'var(--radius-md)', padding: 14, background: 'var(--color-error-light)' }}>
            <div style={{ fontSize: 11, fontWeight: 'var(--font-weight-bold)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-error)', marginBottom: 6 }}>
              Problem
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.7 }}>{rec.problem}</div>
          </div>

          {/* Evidence */}
          <div style={{ borderRadius: 'var(--radius-md)', padding: 14, background: 'var(--color-surface-raised)' }}>
            <div style={{ fontSize: 11, fontWeight: 'var(--font-weight-bold)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-muted)', marginBottom: 6 }}>
              Evidence
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {rec.evidence.map((e, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 14, lineHeight: 1.7 }}>
                  <span style={{ marginTop: 8, display: 'block', width: 5, height: 5, flexShrink: 0, borderRadius: '50%', background: 'var(--color-text-faint)' }} />
                  {e}
                </div>
              ))}
            </div>
          </div>

          {/* Suggested action */}
          <div style={{ borderRadius: 'var(--radius-md)', padding: 14, background: 'var(--color-accent-light)' }}>
            <div style={{ fontSize: 11, fontWeight: 'var(--font-weight-bold)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-accent)', marginBottom: 6 }}>
              Suggested Action
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.7 }}>{rec.suggested_action}</div>
          </div>
        </div>

        {/* Action buttons */}
        {isPending && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <button
              onClick={() => submitDecision.mutate({ id: rec.id, decision: 'approved' })}
              disabled={submitDecision.isPending}
              className="btn btn-success"
            >
              <CheckCircle />
              Approve
            </button>
            <button
              onClick={() => submitDecision.mutate({ id: rec.id, decision: 'rejected' })}
              disabled={submitDecision.isPending}
              className="btn btn-danger-outline"
            >
              <XCircle />
              Reject
            </button>
          </div>
        )}

        {!isPending && (
          <span
            className="badge"
            style={{
              background: rec.status === 'approved' ? 'var(--color-success-light)' : 'var(--color-error-light)',
              color: rec.status === 'approved' ? 'var(--color-success)' : 'var(--color-error)',
              textTransform: 'capitalize',
            }}
          >
            {rec.status}
          </span>
        )}
      </div>

      {/* Simulations */}
      {simulations && simulations.length > 0 && (
        <div className="card">
          <div className="card-header">
            <FlaskConical />
            Simulation Scenarios
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
            {simulations.map((s) => (
              <div
                key={s.scenario}
                style={{ borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', padding: 16 }}
              >
                <div style={{ fontSize: 13, fontWeight: 'var(--font-weight-semibold)', textTransform: 'capitalize', marginBottom: 8 }}>
                  {s.scenario.replace(/_/g, ' ')}
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.4, color: 'var(--color-text-muted)', marginBottom: 8 }}>
                  Spend: {s.expected_effect.monthly_spend_change > 0 ? '+' : ''}{s.expected_effect.monthly_spend_change.toLocaleString()} EGP
                  {' · '}Conv: {s.expected_effect.expected_conversion_change > 0 ? '+' : ''}{s.expected_effect.expected_conversion_change}%
                  {' · '}CPA: {s.expected_effect.expected_cpa_change > 0 ? '+' : ''}{s.expected_effect.expected_cpa_change}%
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {s.assumptions.map((a, i) => (
                    <span
                      key={i}
                      style={{ borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 'var(--font-weight-medium)', background: 'var(--color-surface-raised)', color: 'var(--color-text-secondary)' }}
                    >
                      {a}
                    </span>
                  ))}
                </div>
                <div style={{ marginTop: 8, fontSize: 11, fontWeight: 'var(--font-weight-semibold)', textTransform: 'capitalize', color: 'var(--color-text-faint)' }}>
                  Risk: {s.risk}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
