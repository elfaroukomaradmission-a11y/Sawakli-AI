// TODO: import apiClient from '@/lib/api-client'
import type { AuthResponse } from '@/types'

export async function login(email: string, password: string): Promise<AuthResponse> {
  // TODO: const { data } = await apiClient.post<AuthResponse>('/api/auth/login', { email, password })
  // TODO: return data

  if (email === 'demo@fashionbrandx.com' && password === 'demo') {
    return {
      user: {
        id: 'demo-001',
        name: 'Ahmed Hassan',
        email: 'demo@fashionbrandx.com',
        role: 'admin',
      },
      access_token: 'demo-token-sawakli-2026',
    }
  }
  throw new Error('Invalid email or password')
}
