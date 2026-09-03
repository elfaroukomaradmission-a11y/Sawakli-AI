import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const AUTH_ROUTES = ['/login', '/setup/organization', '/setup/connector']
const PUBLIC_ROUTES = [...AUTH_ROUTES]

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  const hasAuth = request.cookies.has('sawakli-auth')

  const isPublicRoute = PUBLIC_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(route + '/')
  )

  if (!hasAuth && !isPublicRoute) {
    const loginUrl = new URL('/login', request.url)
    return NextResponse.redirect(loginUrl)
  }

  if (hasAuth && AUTH_ROUTES.some((route) => pathname === route)) {
    const dashboardUrl = new URL('/dashboard', request.url)
    return NextResponse.redirect(dashboardUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|api).*)',
  ],
}
