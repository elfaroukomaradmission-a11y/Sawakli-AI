export type User = {
  id: string
  name: string
  email: string
  role?: string
}

export type AuthResponse = {
  user: User
  access_token: string
}

export type RegisterResponse = {
  user: User
  organization: import('./organization').Organization
}

export type MeResponse = {
  user: User
  organization: import('./organization').Organization
}
