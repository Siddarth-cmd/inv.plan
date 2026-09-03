import React from 'react';
import {
  Sliders,
  Shield,
  Activity,
  FileCode,
  ExternalLink,
  GitBranch
} from 'lucide-react';
import InvestigationPlannerView from './InvestigationPlannerView';

const API_BASE = typeof window !== 'undefined' && window.location.origin.includes('5173') ? 'http://localhost:8000/api' : '/api';

export default function App() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      {/* Header Bar */}
      <header style={{ borderBottom: '1px solid var(--border-color)', background: 'rgba(11, 15, 25, 0.90)', backdropFilter: 'blur(16px)', position: 'sticky', top: 0, zIndex: 50, padding: '14px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', maxWidth: '1440px', margin: '0 auto' }}>
          
          {/* Logo & Platform Name */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', padding: '10px', borderRadius: '10px', display: 'flex', boxShadow: '0 0 20px rgba(99, 102, 241, 0.45)' }}>
              <Shield size={24} color="#ffffff" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h1 style={{ fontSize: '18px', fontWeight: '800', letterSpacing: '-0.02em', margin: 0 }}>
                  FinSpectra
                </h1>
                <span className="badge badge-medium" style={{ fontSize: '11px', background: 'rgba(99, 102, 241, 0.2)', border: '1px solid var(--accent-indigo)', color: 'var(--accent-indigo-light)' }}>
                  Investigation Planner Engine v1.0
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: '#34d399', background: 'rgba(16, 185, 129, 0.12)', padding: '2px 8px', borderRadius: '12px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }}></span>
                  API Online
                </span>
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Deterministic 12-Stage Financial Crime Investigation Plan Generator & Traceability Engine
              </p>
            </div>
          </div>

          {/* Quick Links */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <a
              href="http://localhost:8000/api/docs"
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 14px',
                borderRadius: '8px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                fontSize: '12px',
                fontWeight: '600',
                textDecoration: 'none',
                transition: 'all 0.2s'
              }}
            >
              <FileCode size={14} color="var(--accent-cyan)" />
              Swagger API Docs
              <ExternalLink size={12} color="var(--text-muted)" />
            </a>

            <a
              href="https://github.com/Siddarth-cmd/inv.plan"
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 14px',
                borderRadius: '8px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                fontSize: '12px',
                fontWeight: '600',
                textDecoration: 'none',
                transition: 'all 0.2s'
              }}
            >
              <GitBranch size={14} />
              GitHub Repo
              <ExternalLink size={12} color="var(--text-muted)" />
            </a>
          </div>

        </div>
      </header>

      {/* Main Container */}
      <main style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px' }}>
        <InvestigationPlannerView apiBase={API_BASE} />
      </main>
    </div>
  );
}
