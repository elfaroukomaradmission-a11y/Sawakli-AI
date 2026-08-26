export type ActualPoint = {
  date: string
  value: number
}

export type ForecastPoint = {
  date: string
  predicted_value: number
  confidence_low: number
  confidence_high: number
}

export type Forecast = {
  campaign_id: string
  metric: string
  actual: ActualPoint[]
  forecast: ForecastPoint[]
}
