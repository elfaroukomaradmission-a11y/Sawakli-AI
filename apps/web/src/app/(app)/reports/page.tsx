'use client'

import { FileBarChart, Download, Calendar } from 'lucide-react'

export default function ReportsPage() {
  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
        <div className="card-header" style={{ marginBottom: 0 }}>
          <FileBarChart />
          Reports
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: 20 }}>
        <button
          style={{
            display: 'flex',
            height: 34,
            alignItems: 'center',
            gap: 6,
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
            padding: '0 12px',
            fontSize: 12,
            fontWeight: 'var(--font-weight-medium)',
            background: 'var(--color-surface)',
            color: 'var(--color-text-secondary)',
            cursor: 'pointer',
            transition: 'border-color var(--transition)',
          }}
        >
          <Calendar style={{ width: 14, height: 14 }} />
          Last 30 days
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {[
          { name: 'Campaign Performance Summary', date: 'Aug 15, 2026', type: 'PDF' },
          { name: 'Weekly Anomaly Report', date: 'Aug 18, 2026', type: 'CSV' },
          { name: 'Recommendations Audit Log', date: 'Aug 20, 2026', type: 'PDF' },
        ].map((report) => (
          <div
            key={report.name}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              padding: 16,
              transition: 'border-color var(--transition)',
            }}
          >
            <div>
              <div style={{ fontSize: 13, fontWeight: 'var(--font-weight-semibold)' }}>{report.name}</div>
              <div style={{ marginTop: 2, fontSize: 12, color: 'var(--color-text-muted)' }}>
                Generated {report.date} · {report.type}
              </div>
            </div>
            <button
              style={{
                display: 'flex',
                height: 34,
                alignItems: 'center',
                gap: 6,
                borderRadius: 'var(--radius-md)',
                padding: '0 12px',
                fontSize: 12,
                fontWeight: 'var(--font-weight-semibold)',
                background: 'var(--color-accent-light)',
                color: 'var(--color-accent)',
                border: 'none',
                cursor: 'pointer',
                transition: 'background var(--transition)',
              }}
            >
              <Download style={{ width: 14, height: 14 }} />
              Download
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
