import type { Simulation } from '@/types'

export const mockSimulations: Simulation[] = [
  {
    id: 'sim-001',
    recommendation_id: 'rec-001',
    scenario_type: 'budget_decrease_20',
    projected_spend: 14800,
    projected_conversions: 119,
    projected_cpa: 124.4,
    projected_roas: 3.4,
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'sim-002',
    recommendation_id: 'rec-001',
    scenario_type: 'budget_increase_15',
    projected_spend: 21275,
    projected_conversions: 129,
    projected_cpa: 164.9,
    projected_roas: 2.9,
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'sim-003',
    recommendation_id: 'rec-001',
    scenario_type: 'pause',
    projected_spend: 0,
    projected_conversions: 0,
    projected_cpa: 0,
    projected_roas: 0,
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
]
