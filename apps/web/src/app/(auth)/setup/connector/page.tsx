'use client'

import { useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  AlertCircle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  FileSpreadsheet,
  FileUp,
  Link2,
  Plug,
  ShieldCheck,
  UploadCloud,
} from 'lucide-react'
import { setSession, DEMO_SESSION, getSession } from '@/lib/mock-auth'

type SourceChoice = 'demo' | 'csv' | 'ga4' | 'google-ads' | null

const CONNECTORS = [
  { id: 'ga4', name: 'Google Analytics 4', detail: 'OAuth connection', icon: BarChart3 },
  { id: 'google-ads', name: 'Google Ads', detail: 'OAuth connection', icon: Link2 },
] as const

export default function ConnectorSetupPage() {
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const [source, setSource] = useState<SourceChoice>(null)
  const [fileName, setFileName] = useState('')
  const [fileSize, setFileSize] = useState<number | null>(null)
  const [error, setError] = useState('')

  function handleFile(file: File | undefined) {
    setError('')
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setFileName('')
      setFileSize(null)
      setSource(null)
      setError('Choose a CSV file to continue.')
      return
    }
    setFileName(file.name)
    setFileSize(file.size)
    setSource('csv')
  }

  function continueToDashboard() {
    if (!source) {
      setError('Choose demo data or select a CSV before continuing.')
      return
    }
    if (source === 'ga4' || source === 'google-ads') {
      setError('OAuth authorization for this connector is not available yet. Choose demo data or CSV to continue.')
      return
    }
    if (!getSession()) setSession(DEMO_SESSION)
    router.push('/dashboard')
  }

  function chooseDemo() {
    setError('')
    setFileName('')
    setFileSize(null)
    setSource('demo')
  }

  function chooseConnector(connector: 'ga4' | 'google-ads') {
    setError('')
    setFileName('')
    setFileSize(null)
    setSource(connector)
  }

  return (
    <div className="setup-shell setup-shell-wide">
      <div className="setup-step"><Plug /> Step 2 of 2</div>

      <h1>Bring in your marketing data</h1>
      <p className="setup-lede">Start with safe demo data or import a CSV. OAuth connectors will return here with a connection status after authorization.</p>

      {error && <div className="error-alert" role="alert"><AlertCircle /> {error}</div>}

      <div className="source-list">
        {CONNECTORS.map(({ id, name, detail, icon: Icon }) => (
          <button
            type="button"
            className={`source-row source-choice ${source === id ? 'selected' : ''}`}
            key={name}
            onClick={() => chooseConnector(id)}
          >
            <div className="source-icon"><Icon /></div>
            <div className="source-copy">
              <strong>{name}</strong>
              <span>{detail}</span>
            </div>
            <span className={`source-status ${source === id ? 'selected-status' : ''}`}>
              {source === id ? <CheckCircle2 /> : <span className="status-dot" />}
              {source === id ? 'Selected' : 'Available'}
            </span>
          </button>
        ))}
      </div>

      <div className="setup-divider"><span>or use the demo path</span></div>

      <button type="button" className={`demo-choice ${source === 'demo' ? 'selected' : ''}`} onClick={chooseDemo}>
        <div className="demo-choice-icon"><FileSpreadsheet /></div>
        <span><strong>Load Sawakli demo data</strong><small>Explore the workspace with a prepared campaign dataset.</small></span>
        {source === 'demo' && <CheckCircle2 className="choice-check" />}
      </button>

      <div className={`upload-zone ${source === 'csv' ? 'selected' : ''}`}>
        <input ref={inputRef} type="file" accept=".csv,text/csv" onChange={(event) => handleFile(event.target.files?.[0])} hidden />
        {source === 'csv' ? <FileUp className="upload-icon" /> : <UploadCloud className="upload-icon" />}
        {fileName ? (
          <>
            <strong>{fileName}</strong>
            <span>{formatFileSize(fileSize ?? 0)} · Ready to import</span>
          </>
        ) : (
          <>
            <strong>Import a CSV file</strong>
            <span>Campaign metrics stay in your workspace scope.</span>
          </>
        )}
        <button type="button" className="btn btn-secondary upload-button" onClick={() => inputRef.current?.click()}>
          {fileName ? 'Choose another file' : 'Choose CSV'}
        </button>
      </div>

      <div className="safe-note"><ShieldCheck /><span>No API keys or provider tokens are requested on this screen. Selected connectors still require OAuth authorization.</span></div>

      <button type="button" onClick={continueToDashboard} className="btn btn-primary setup-submit">
        <ArrowRight /> Continue to workspace
      </button>

      <p className="setup-back"><Link href="/setup/organization">Back to workspace setup</Link></p>
    </div>
  )
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
