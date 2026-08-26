import type { Anomaly } from '@/types'

export const mockAnomalies: Anomaly[] = [
  {
    id: 'anom-001',
    campaign_id: 'camp-001',
    metric: 'CPA',
    severity: 'high',
    detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    title: 'CPA spike on Summer Sale',
    description: 'CPA rose 45% to 166.6 EGP (vs 115 EGP 14-day avg)',
    evidence: [
      'CPA increased from 115 EGP to 166.6 EGP in the last 24 hours',
      'Click-through rate remained stable at 2.1%',
      'Conversion rate dropped from 3.8% to 2.6%',
    ],
  },
  {
    id: 'anom-002',
    campaign_id: 'camp-002',
    metric: 'CTR',
    severity: 'medium',
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    title: 'CTR declining on Brand Awareness',
    description: 'CTR dropped 12% week-over-week',
    evidence: [
      'CTR fell from 2.05% to 1.8% over the past 7 days',
      'Impressions increased by 8%, suggesting ad fatigue',
      'Frequency reached 4.2 in the target audience segment',
    ],
  },
]
