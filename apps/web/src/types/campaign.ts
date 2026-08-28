export type CampaignPlatform = 'meta' | 'google'

export type CampaignStatus = 'active' | 'paused' | 'removed' | 'unknown'

export type HealthStatus = 'strong' | 'average' | 'weak'

export type Campaign = {
  id: string
  organization_id: string
  name: string
  platform: CampaignPlatform
  objective: string
  status: CampaignStatus
  budget?: number
  start_date?: string
  end_date?: string
  spend: number
  clicks: number
  conversions: number
  ctr: number
  cpc: number
  cpa: number
  roas: number
  health_status: HealthStatus
}

export type TimeSeriesPoint = {
  date: string
  spend: number
  clicks: number
  conversions: number
  cpa: number
  roas: number
  ctr: number
}

export type CampaignDetails = {
  campaign: Campaign
  time_series: TimeSeriesPoint[]
  related_anomalies: import('./anomaly').Anomaly[]
  related_recommendations: import('./recommendation').Recommendation[]
}
