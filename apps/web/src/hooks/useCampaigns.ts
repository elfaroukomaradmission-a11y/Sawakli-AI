import { useQuery } from '@tanstack/react-query'
import { getCampaigns, getCampaignDetails } from '@/services/campaigns.service'
import type { Campaign, CampaignDetails } from '@/types'

export function useCampaigns(orgId: string) {
  return useQuery<Campaign[]>({
    queryKey: ['campaigns', orgId],
    queryFn: () => getCampaigns(orgId),
    enabled: !!orgId,
  })
}

export function useCampaignDetails(id: string) {
  return useQuery<CampaignDetails>({
    queryKey: ['campaign-details', id],
    queryFn: () => getCampaignDetails(id),
    enabled: !!id,
  })
}
