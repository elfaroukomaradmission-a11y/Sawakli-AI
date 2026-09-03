import type { Anomaly } from '@/types'

export const mockAnomalies: Anomaly[] = [
  {
    id: 'anom-001',
    model_run_id: 'run-001',
    organization_id: 'org-001',
    campaign_id: 'camp-001',
    metric_name: 'CPA',
    severity: 'high',
    direction: 'above',
    anomaly_score: 0.92,
    detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'anom-002',
    model_run_id: 'run-001',
    organization_id: 'org-001',
    campaign_id: 'camp-002',
    metric_name: 'CTR',
    severity: 'medium',
    direction: 'below',
    anomaly_score: 0.74,
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
  },
]
