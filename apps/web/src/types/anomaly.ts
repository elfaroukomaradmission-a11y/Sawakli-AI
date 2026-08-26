export type AnomalySeverity = 'high' | 'medium' | 'low'

export type Anomaly = {
  id: string
  campaign_id: string
  metric: string
  severity: AnomalySeverity
  detected_at: string
  title: string
  description: string
  evidence: string[]
}
