export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <main
      style={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--color-background)',
      }}
    >
      {children}
    </main>
  )
}
