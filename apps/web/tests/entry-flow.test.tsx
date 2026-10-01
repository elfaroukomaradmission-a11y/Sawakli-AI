import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerPush = vi.hoisted(() => vi.fn())

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: routerPush }),
}))

import ConnectorSetupPage from '../src/app/(auth)/setup/connector/page'

describe('entry flow', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('requires a source before opening the workspace', () => {
    render(<ConnectorSetupPage />)

    fireEvent.click(screen.getByRole('button', { name: /continue to workspace/i }))

    expect(screen.getByRole('alert')).toHaveTextContent('Choose demo data or select a CSV')
  })

  it('accepts the demo path and presents safe source status', () => {
    routerPush.mockReset()
    render(<ConnectorSetupPage />)

    fireEvent.click(screen.getByRole('button', { name: /load sawakli demo data/i }))
    fireEvent.click(screen.getByRole('button', { name: /continue to workspace/i }))

    expect(routerPush).toHaveBeenCalledWith('/dashboard')
    expect(screen.getByText(/no api keys or provider tokens/i)).toBeInTheDocument()
  })
})
