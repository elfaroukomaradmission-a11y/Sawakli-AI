import type { Simulation } from '@/types'

export const mockSimulations: Simulation[] = [
  {
    recommendation_id: 'rec-001',
    scenario: 'budget_reduction',
    assumptions: [
      'Reduce bids on underperforming ad groups by 20%',
      'Pause keywords with CPA above 200 EGP',
      'Reallocate 15% of budget to retargeting',
    ],
    expected_effect: {
      monthly_spend_change: -2775,
      expected_conversion_change: 8,
      expected_cpa_change: -25,
      expected_roas_change: 0.6,
    },
    risk: 'Medium — may reduce reach on some keywords temporarily',
  },
  {
    recommendation_id: 'rec-001',
    scenario: 'budget_increase',
    assumptions: [
      'Increase overall campaign budget by 20%',
      'Expand keyword targeting to broader match types',
      'Add new ad creatives for A/B testing',
    ],
    expected_effect: {
      monthly_spend_change: 3700,
      expected_conversion_change: 18,
      expected_cpa_change: -10,
      expected_roas_change: 0.3,
    },
    risk: 'High — increased spend may not yield proportional returns',
  },
  {
    recommendation_id: 'rec-001',
    scenario: 'pause',
    assumptions: [
      'Pause Summer Sale Campaign entirely',
      'Redistribute budget to Retargeting and Brand Awareness',
      'Monitor competitor activity during pause',
    ],
    expected_effect: {
      monthly_spend_change: -18500,
      expected_conversion_change: -65,
      expected_cpa_change: 0,
      expected_roas_change: -2.8,
    },
    risk: 'High — loses all campaign momentum and market presence',
  },
]
