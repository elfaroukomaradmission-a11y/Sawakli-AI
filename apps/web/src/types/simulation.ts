export type SimulationScenario = 'budget_reduction' | 'budget_increase' | 'pause'

export type ExpectedEffect = {
  monthly_spend_change: number
  expected_conversion_change: number
  expected_cpa_change: number
  expected_roas_change: number
}

export type Simulation = {
  recommendation_id: string
  scenario: SimulationScenario
  assumptions: string[]
  expected_effect: ExpectedEffect
  risk: string
}
