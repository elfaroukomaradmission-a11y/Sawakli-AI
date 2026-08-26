// TODO: import apiClient from '@/lib/api-client'
import type { Recommendation, RecommendationDecision, DecisionResponse, Simulation } from '@/types'
import { mockRecommendations } from '@/lib/mock-data/recommendations'
import { mockSimulations } from '@/lib/mock-data/simulations'

export async function getRecommendations(_orgId: string): Promise<Recommendation[]> {
  // TODO: const { data } = await apiClient.get<Recommendation[]>('/api/recommendations', { params: { organization_id: orgId } })
  // TODO: return data
  return mockRecommendations
}

export async function getRecommendation(id: string): Promise<Recommendation> {
  // TODO: const { data } = await apiClient.get<Recommendation>(`/api/recommendations/${id}`)
  // TODO: return data
  return mockRecommendations.find((r) => r.id === id) ?? mockRecommendations[0]
}

export async function simulateRecommendation(id: string): Promise<Simulation[]> {
  // TODO: const { data } = await apiClient.get<Simulation>(`/api/recommendations/${id}/simulate`)
  // TODO: return data
  return mockSimulations.filter((s) => s.recommendation_id === id)
}

export async function submitDecision(
  id: string,
  decision: RecommendationDecision,
  comment?: string
): Promise<DecisionResponse> {
  // TODO: const { data } = await apiClient.post<DecisionResponse>(`/api/recommendations/${id}/decision`, { decision, comment })
  // TODO: return data
  void comment
  return {
    recommendation_id: id,
    status: decision === 'approved' ? 'approved' : 'rejected',
    decision_logged_at: new Date().toISOString(),
  }
}
