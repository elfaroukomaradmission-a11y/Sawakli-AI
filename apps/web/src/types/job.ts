export type JobStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED'

export type Job = {
  job_id: string
  status: JobStatus
  message?: string
}
