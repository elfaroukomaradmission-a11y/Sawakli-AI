export type Forecast = {
  id: string
  model_run_id: string
  organization_id: string
  campaign_id: string
  metric_name: string
  forecast_date: string
  value: number
  ci_lower?: number
  ci_upper?: number
  model_used?: string
  created_at: string
}
