type ConnectorSetupResponse = {
  data_source_id: string
  provider: string
  status: string
  sync_status: string | null
  last_synced_at: string | null
}

type CsvUploadResponse = {
  data_source_id: string
  row_count: number
  parsed_rows: Array<Record<string, unknown>>
  parse_warnings: string[]
  sync_status: string
  last_synced_at: string
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function parseError(response: Response) {
  const body = (await response.json().catch(() => null)) as { detail?: { message?: string } | string } | null
  if (typeof body?.detail === 'string') return body.detail
  return body?.detail?.message ?? 'The connector request could not be completed.'
}

export async function setupCsvSource(accessToken: string): Promise<ConnectorSetupResponse> {
  const response = await fetch(`${API_URL}/api/connectors/setup`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) throw new Error(await parseError(response))
  return response.json() as Promise<ConnectorSetupResponse>
}

export async function uploadCsv(
  accessToken: string,
  dataSourceId: string,
  file: File,
): Promise<CsvUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${API_URL}/api/connectors/csv/${dataSourceId}/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
    body: form,
  })
  if (!response.ok) throw new Error(await parseError(response))
  return response.json() as Promise<CsvUploadResponse>
}