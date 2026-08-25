export type User = {
  id: string
  name: string
  email: string
  role: string
}

export type AuthResponse = {
  user: User
  access_token: string
}
