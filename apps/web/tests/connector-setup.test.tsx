import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ConnectorSetupPage from '@/app/(auth)/setup/connector/page'
import { getSession } from '@/lib/session'
import { createCsvConnector, uploadCsv } from '@/services/connectors.service'

const push = vi.fn()

vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
vi.mock('@/lib/session', () => ({ getSession: vi.fn() }))
vi.mock('@/services/connectors.service', () => ({
  createCsvConnector: vi.fn(),
  uploadCsv: vi.fn(),
}))

describe('ConnectorSetupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getSession).mockReturnValue({
      access_token: 'test-token',
      user: { id: 'user-1', name: 'Test User', email: 'test@example.com' },
      organization: { id: 'org-1', name: 'Test workspace' },
    })
  })

  it('uploads a CSV through API-03 and labels the result as validated', async () => {
    vi.mocked(createCsvConnector).mockResolvedValue({
      data_source_id: 'source-1', provider: 'csv_demo', status: 'disconnected',
    })
    vi.mocked(uploadCsv).mockResolvedValue({
      data_source_id: 'source-1', provider: 'csv_demo', row_count: 4, parsed_rows: [], parse_warnings: [],
    })
    render(<ConnectorSetupPage />)

    const file = new File(['date,spend\n2026-01-01,10'], 'campaigns.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload and validate CSV' }))

    await waitFor(() => expect(uploadCsv).toHaveBeenCalledWith('test-token', 'source-1', file))
    expect(createCsvConnector).toHaveBeenCalledWith('test-token')
    expect(screen.getByText('CSV validated')).toBeInTheDocument()
    expect(screen.getByText(/data processing and dashboard freshness are unavailable/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue to demo dashboard' })).toBeEnabled()
  })

  it('rejects a non-CSV file before an API request', () => {
    render(<ConnectorSetupPage />)
    fireEvent.change(screen.getByLabelText('CSV file'), {
      target: { files: [new File(['not csv'], 'notes.txt', { type: 'text/plain' })] },
    })

    expect(screen.getByRole('alert')).toHaveTextContent('Choose a CSV file to continue.')
    expect(createCsvConnector).not.toHaveBeenCalled()
  })
})
