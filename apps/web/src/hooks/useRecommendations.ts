import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getRecommendations, getRecommendation, simulateRecommendation, submitDecision } from '@/services/recommendations.service'
import type { Recommendation, RecommendationDecision, DecisionResponse, Simulation } from '@/types'

export function useRecommendations(orgId: string) {
  return useQuery<Recommendation[]>({
    queryKey: ['recommendations', orgId],
    queryFn: () => getRecommendations(orgId),
    enabled: !!orgId,
  })
}

export function useRecommendation(id: string) {
  return useQuery<Recommendation>({
    queryKey: ['recommendation', id],
    queryFn: () => getRecommendation(id),
    enabled: !!id,
  })
}

export function useSimulations(id: string) {
  return useQuery<Simulation[]>({
    queryKey: ['simulations', id],
    queryFn: () => simulateRecommendation(id),
    enabled: !!id,
  })
}

export function useSubmitDecision() {
  const queryClient = useQueryClient()

  return useMutation<
    DecisionResponse,
    Error,
    { id: string; decision: RecommendationDecision; comment?: string }
  >({
    mutationFn: ({ id, decision, comment }) => submitDecision(id, decision, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations'] })
    },
  })
}
