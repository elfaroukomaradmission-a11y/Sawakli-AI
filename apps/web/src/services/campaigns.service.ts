// TODO: import apiClient from '@/lib/api-client'
import type { Campaign, CampaignDetails, Anomaly } from '@/types'
import { mockCampaigns } from '@/lib/mock-data/campaigns'
import { mockAnomalies } from '@/lib/mock-data/anomalies'

export async function getCampaigns(_orgId: string): Promise<Campaign[]> {
  // TODO: const { data } = await apiClient.get<Campaign[]>('/api/campaigns', { params: { organization_id: orgId } })
  // TODO: return data
  return mockCampaigns
}

export async function getCampaignDetails(id: string): Promise<CampaignDetails> {
  // TODO: const { data } = await apiClient.get<CampaignDetails>(`/api/campaigns/${id}/details`)
  // TODO: return data
  const campaign = mockCampaigns.find((c) => c.id === id) ?? mockCampaigns[0]
  return {
    campaign,
    time_series: [],
    related_anomalies: mockAnomalies.filter((a) => a.campaign_id === id),
    related_recommendations: [],
  }
}

export async function getAnomalies(): Promise<Anomaly[]> {
  // TODO: fetch from API
  return mockAnomalies
}
