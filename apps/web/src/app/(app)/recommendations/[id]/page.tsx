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
        <span>{rec.problem.slice(0, 60)}{rec.problem.length > 60 ? '...' : ''}</span>
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
              {Math.round(rec.confidence_score * 100)}% confidence
            </span>
            <span
              className="badge"
              style={{
                background: rec.risk_rating === 'high' ? 'var(--color-error-light)' : rec.risk_rating === 'medium' ? 'var(--color-warning-light)' : 'var(--color-success-light)',
                color: rec.risk_rating === 'high' ? 'var(--color-error)' : rec.risk_rating === 'medium' ? 'var(--color-warning)' : 'var(--color-success)',
                textTransform: 'capitalize',
              }}
            >
              {rec.risk_rating} risk
            </span>
          </div>
        </div>

        {/* Title */}
        <h2 style={{ fontSize: 17, fontWeight: 'var(--font-weight-bold)', lineHeight: 1.35, letterSpacing: '-0.01em', marginBottom: 18 }}>
          {rec.problem}
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
              background: (rec.status === 'approved' || rec.status === 'marked_done')
                ? 'var(--color-success-light)'
                : rec.status === 'needs_review'
                  ? 'var(--color-warning-light)'
                  : 'var(--color-error-light)',
              color: (rec.status === 'approved' || rec.status === 'marked_done')
                ? 'var(--color-success)'
                : rec.status === 'needs_review'
                  ? 'var(--color-warning)'
                  : 'var(--color-error)',
              textTransform: 'capitalize',
            }}
          >
            {rec.status.replace(/_/g, ' ')}
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
                key={s.scenario_type}
                style={{ borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', padding: 16 }}
              >
                <div style={{ fontSize: 13, fontWeight: 'var(--font-weight-semibold)', textTransform: 'capitalize', marginBottom: 8 }}>
                  {s.scenario_type.replace(/_/g, ' ')}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, lineHeight: 1.4, color: 'var(--color-text-muted)' }}>
                  <span>Spend: {s.projected_spend.toLocaleString()} EGP</span>
                  <span>Conversions: {s.projected_conversions.toLocaleString()}</span>
                  <span>CPA: {s.projected_cpa.toFixed(1)} EGP</span>
                  <span>ROAS: {s.projected_roas.toFixed(1)}x</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
