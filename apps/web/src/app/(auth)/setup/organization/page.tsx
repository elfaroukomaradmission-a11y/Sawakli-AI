'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Building2, ArrowRight } from 'lucide-react'

export default function OrganizationSetupPage() {
  const router = useRouter()
  const [orgName, setOrgName] = useState('')
  const [industry, setIndustry] = useState('Fashion & Apparel')
  const [adSpend, setAdSpend] = useState('10,000 – 50,000 EGP')
  const [currency, setCurrency] = useState('EGP — Egyptian Pound')

  function handleContinue(e: React.FormEvent) {
    e.preventDefault()
    router.push('/setup/connector')
  }

  return (
    <div
      style={{
        width: '100%',
        maxWidth: 480,
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
        padding: '40px 32px',
        background: 'var(--color-surface)',
        boxShadow: 'var(--shadow-md)',
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          borderRadius: 4,
          padding: '4px 10px',
          fontSize: 12,
          fontWeight: 'var(--font-weight-semibold)',
          background: 'var(--color-accent-light)',
          color: 'var(--color-accent)',
          marginBottom: 16,
        }}
      >
        <Building2 style={{ width: 14, height: 14 }} />
        Step 1 of 2
      </div>

      <h1 style={{ fontSize: 18, fontWeight: 'var(--font-weight-bold)', marginBottom: 4 }}>
        Create your organization
      </h1>
      <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 28 }}>
        Set up your business workspace to start connecting ad platforms.
      </p>

      <form onSubmit={handleContinue}>
        <div className="form-group">
          <label htmlFor="orgName" className="form-label">Organization name</label>
          <input
            id="orgName"
            type="text"
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            required
            className="form-input"
          />
        </div>

        <div className="form-group">
          <label htmlFor="industry" className="form-label">Industry</label>
          <select
            id="industry"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className="form-input"
            style={{ appearance: 'none', paddingRight: 32 }}
          >
            <option>Fashion &amp; Apparel</option>
            <option>E-commerce</option>
            <option>Retail</option>
            <option>Other</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="adSpend" className="form-label">Monthly ad spend range</label>
          <select
            id="adSpend"
            value={adSpend}
            onChange={(e) => setAdSpend(e.target.value)}
            className="form-input"
            style={{ appearance: 'none', paddingRight: 32 }}
          >
            <option>10,000 – 50,000 EGP</option>
            <option>50,000 – 200,000 EGP</option>
            <option>200,000+ EGP</option>
          </select>
          <p style={{ marginTop: 4, fontSize: 11, color: 'var(--color-text-faint)' }}>
            Helps Sawakli calibrate recommendations for your budget.
          </p>
        </div>

        <div className="form-group">
          <label htmlFor="currency" className="form-label">Default currency</label>
          <select
            id="currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="form-input"
            style={{ appearance: 'none', paddingRight: 32 }}
          >
            <option>EGP — Egyptian Pound</option>
            <option>USD — US Dollar</option>
            <option>EUR — Euro</option>
          </select>
        </div>

        <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
          <ArrowRight style={{ width: 16, height: 16 }} />
          Continue to Connectors
        </button>
      </form>

      <p style={{ marginTop: 16, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
        <Link href="/login" style={{ fontWeight: 'var(--font-weight-medium)', color: 'var(--color-accent)' }}>
          Back to Login
        </Link>
      </p>
    </div>
  )
}
