export type SimulationScenario = 'budget_decrease_20' | 'budget_increase_15' | 'pause'

export type Simulation = {
  id: string
  recommendation_id: string
  scenario_type: SimulationScenario
  projected_spend: number
  projected_conversions: number
  projected_cpa: number
  projected_roas: number
  created_at: string
}
