'use client'

import { Sidebar } from '@/components/layout/sidebar'
import { Topbar } from '@/components/layout/topbar'
import { usePathname } from 'next/navigation'

const ROUTE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/campaigns': 'Campaigns',
  '/recommendations': 'Recommendations',
  '/reports': 'Reports',
  '/settings': 'Settings',
}

function getTitle(pathname: string): string {
  if (ROUTE_TITLES[pathname]) return ROUTE_TITLES[pathname]
  if (pathname.startsWith('/campaigns/')) return 'Campaign Details'
  if (pathname.startsWith('/recommendations/')) return 'Recommendation Details'
  return 'Sawakli AI'
}

export default function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const title = getTitle(pathname)

  return (
    <>
      <Sidebar />
      <div style={{ minHeight: '100vh', marginLeft: 'var(--sidebar-w)' }}>
        <Topbar title={title} />
        <div style={{ padding: 'var(--spacing-6)' }}>{children}</div>
      </div>
    </>
  )
}
