export type ConnectorSetupResponse = {
  data_source_id: string
  provider: string
  status: string
}

export type CsvUploadResponse = {
  data_source_id: string
  provider: string
  row_count: number
  parsed_rows: Array<Record<string, unknown>>
  parse_warnings: string[]
}

export type ConnectorStatusResponse = {
  data_source_id: string
  connected: boolean
  token_valid: boolean
  last_successful_call_at: string | null
}
