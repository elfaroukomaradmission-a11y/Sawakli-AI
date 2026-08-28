export type JobStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'CANCELLED' | 'PARTIAL_SUCCESS'

export type JobPriority = 'HIGH' | 'LOW'

export type Job = {
  id: string
  organization_id: string
  status: JobStatus
  priority: JobPriority
  campaign_ids?: string[]
  created_at: string
  claimed_at?: string
  message?: string
}
