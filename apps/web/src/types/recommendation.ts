export type RecommendationStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'marked_done'
  | 'needs_review'

export type RiskRating = 'high' | 'medium' | 'low'

export type RecommendationDecision = 'approved' | 'rejected'

export type Recommendation = {
  id: string
  model_run_id: string
  organization_id: string
  campaign_id: string
  campaign_name: string
  source_anomaly_id?: string
  problem: string
  evidence: string[]
  suggested_action: string
  confidence_score: number
  risk_rating: RiskRating
  severity?: number
  status: RecommendationStatus
  created_at: string
}

export type DecisionResponse = {
  recommendation_id: string
  status: RecommendationStatus
  decision_logged_at: string
}
