import { useQuery } from '@tanstack/react-query'
import { getAnomalies } from '@/services/campaigns.service'
import type { Anomaly } from '@/types'

export function useAnomalies() {
  return useQuery<Anomaly[]>({
    queryKey: ['anomalies'],
    queryFn: () => getAnomalies(),
  })
}
