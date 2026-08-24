export type RecommendationStatus = 'pending' | 'approved' | 'rejected'

export type RecommendationRisk = 'high' | 'medium' | 'low'

export type RecommendationDecision = 'approved' | 'rejected'

export type Recommendation = {
  id: string
  campaign_id: string
  campaign_name: string
  title: string
  problem: string
  evidence: string[]
  suggested_action: string
  confidence: number
  risk: RecommendationRisk
  status: RecommendationStatus
}

export type DecisionResponse = {
  recommendation_id: string
  status: RecommendationStatus
  decision_logged_at: string
}
