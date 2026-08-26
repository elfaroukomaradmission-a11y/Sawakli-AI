'use client'

import { useSyncExternalStore } from 'react'
import { useTheme } from 'next-themes'
import { Sun, Moon } from 'lucide-react'
import styles from './topbar.module.css'

const emptySubscribe = () => () => {}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false)

  if (!mounted) return <div style={{ width: 32, height: 32 }} />

  return (
    <button
      onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
      className={styles.themeToggle}
      aria-label="Toggle dark mode"
    >
      {resolvedTheme === 'dark' ? <Sun /> : <Moon />}
    </button>
  )
}

export function Topbar({ title }: { title: string }) {
  return (
    <header className={styles.topbar}>
      <h1 className={styles.title}>{title}</h1>
      <ThemeToggle />
    </header>
  )
}
