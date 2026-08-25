import type { Recommendation } from '@/types'

export const mockRecommendations: Recommendation[] = [
  {
    id: 'rec-001',
    campaign_id: 'camp-001',
    campaign_name: 'Summer Sale Campaign',
    title: 'Reduce CPA by 15%',
    problem:
      'Summer Sale Campaign CPA has risen 45% above the 14-day average, reaching 166.6 EGP vs the normal 115 EGP. This is consuming budget without proportional conversions.',
    evidence: [
      'CPA increased from 115 EGP to 166.6 EGP in the last 24 hours',
      'Conversion rate dropped from 3.8% to 2.6% while CPC remained stable',
      'Similar campaigns in the fashion vertical average 110–130 EGP CPA',
    ],
    suggested_action:
      'Reduce bids on underperforming ad groups by 20% and pause keywords with CPA above 200 EGP. Reallocate 15% of budget to the retargeting campaign which has a 90.3 EGP CPA.',
    confidence: 82,
    risk: 'medium',
    status: 'pending',
  },
  {
    id: 'rec-002',
    campaign_id: 'camp-002',
    campaign_name: 'Brand Awareness',
    title: 'Reallocate budget to top performers',
    problem:
      'Brand Awareness campaign CTR has declined 12% week-over-week, indicating ad fatigue in the target audience.',
    evidence: [
      'CTR dropped from 2.05% to 1.8% over 7 days',
      'Ad frequency reached 4.2, above the 3.0 fatigue threshold',
      'Creative has been running unchanged for 21 days',
    ],
    suggested_action:
      'Refresh ad creatives and reduce daily budget by 10%. Shift freed budget to Retargeting — Cart Abandoners which shows strong ROAS of 4.5.',
    confidence: 78,
    risk: 'medium',
    status: 'pending',
  },
  {
    id: 'rec-003',
    campaign_id: 'camp-003',
    campaign_name: 'Retargeting — Cart Abandoners',
    title: 'Increase bid on top-converting keywords',
    problem:
      'Retargeting campaign is impression-limited on its best-performing keywords, missing potential conversions.',
    evidence: [
      'Top 5 keywords have impression share of only 62%',
      'These keywords convert at 5.1%, double the campaign average',
      'Estimated additional daily conversions: 8–12',
    ],
    suggested_action:
      'Increase bids by 15% on the top 5 converting keywords to capture additional impression share.',
    confidence: 75,
    risk: 'low',
    status: 'approved',
  },
]
