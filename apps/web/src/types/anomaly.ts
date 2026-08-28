export type AnomalySeverity = 'high' | 'medium' | 'low'

export type AnomalyDirection = 'above' | 'below'

export type Anomaly = {
  id: string
  model_run_id: string
  organization_id: string
  campaign_id: string
  metric_name: string
  detected_at: string
  anomaly_score: number
  severity: AnomalySeverity
  direction: AnomalyDirection
  created_at: string
}
