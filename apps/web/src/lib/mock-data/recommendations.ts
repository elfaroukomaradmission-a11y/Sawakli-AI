import type { Recommendation } from '@/types'

export const mockRecommendations: Recommendation[] = [
  {
    id: 'rec-001',
    model_run_id: 'run-001',
    organization_id: 'org-001',
    campaign_id: 'camp-001',
    campaign_name: 'Summer Sale Campaign',
    source_anomaly_id: 'anom-001',
    problem:
      'Summer Sale Campaign CPA has risen 45% above the 14-day average, reaching 166.6 EGP vs the normal 115 EGP. This is consuming budget without proportional conversions.',
    evidence: [
      'CPA increased from 115 EGP to 166.6 EGP in the last 24 hours',
      'Conversion rate dropped from 3.8% to 2.6% while CPC remained stable',
      'Similar campaigns in the fashion vertical average 110–130 EGP CPA',
    ],
    suggested_action:
      'Reduce bids on underperforming ad groups by 20% and pause keywords with CPA above 200 EGP. Reallocate 15% of budget to the retargeting campaign which has a 90.3 EGP CPA.',
    confidence_score: 0.82,
    risk_rating: 'medium',
    severity: 3,
    status: 'pending',
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'rec-002',
    model_run_id: 'run-001',
    organization_id: 'org-001',
    campaign_id: 'camp-002',
    campaign_name: 'Brand Awareness',
    source_anomaly_id: 'anom-002',
    problem:
      'Brand Awareness campaign CTR has declined 12% week-over-week, indicating ad fatigue in the target audience.',
    evidence: [
      'CTR dropped from 2.05% to 1.8% over 7 days',
      'Ad frequency reached 4.2, above the 3.0 fatigue threshold',
      'Creative has been running unchanged for 21 days',
    ],
    suggested_action:
      'Refresh ad creatives and reduce daily budget by 10%. Shift freed budget to Retargeting — Cart Abandoners which shows strong ROAS of 4.5.',
    confidence_score: 0.78,
    risk_rating: 'medium',
    severity: 2,
    status: 'pending',
    created_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'rec-003',
    model_run_id: 'run-001',
    organization_id: 'org-001',
    campaign_id: 'camp-003',
    campaign_name: 'Retargeting — Cart Abandoners',
    problem:
      'Retargeting campaign is impression-limited on its best-performing keywords, missing potential conversions.',
    evidence: [
      'Top 5 keywords have impression share of only 62%',
      'These keywords convert at 5.1%, double the campaign average',
      'Estimated additional daily conversions: 8–12',
    ],
    suggested_action:
      'Increase bids by 15% on the top 5 converting keywords to capture additional impression share.',
    confidence_score: 0.75,
    risk_rating: 'low',
    severity: 1,
    status: 'approved',
    created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
  },
]
