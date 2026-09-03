import React, { useState, useEffect } from 'react';
import {
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Play,
  FileText,
  Search,
  Code,
  Shield,
  Layers,
  ArrowRight,
  RefreshCw,
  Info,
  ChevronRight,
  Database,
  Activity,
  CheckSquare
} from 'lucide-react';

export default function InvestigationPlannerView({ apiBase, authToken }) {
  const [scenarios, setScenarios] = useState({});
  const [selectedScenarioKey, setSelectedScenarioKey] = useState('1');
  const [plannerMode, setPlannerMode] = useState('scenario'); // 'scenario' | 'custom'
  const [customAlertJson, setCustomAlertJson] = useState('');
  const [generatedPlan, setGeneratedPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeSection, setActiveSection] = useState('summary'); // 'summary', 'facts', 'red_flags', 'questions', 'evidence', 'sequence', 'decisions', 'json'
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchScenarios();
  }, []);

  const fetchScenarios = async () => {
    try {
      const res = await fetch(`${apiBase}/investigation-planner/scenarios`);
      if (res.ok) {
        const data = await res.json();
        const scMap = data.scenarios || {};
        setScenarios(scMap);
        if (scMap['1']) {
          setCustomAlertJson(JSON.stringify(scMap['1'].alert, null, 2));
          // Auto-run first scenario on initial load
          runPlanner(scMap['1'].alert);
        }
      }
    } catch (err) {
      console.error('Failed to load scenarios:', err);
    }
  };

  const handleSelectScenario = (key) => {
    setSelectedScenarioKey(key);
    if (scenarios[key]) {
      setCustomAlertJson(JSON.stringify(scenarios[key].alert, null, 2));
      runPlanner(scenarios[key].alert);
    }
  };

  const runPlanner = async (alertPayload) => {
    setLoading(true);
    setError(null);
    try {
      let payload = alertPayload;
      if (!payload) {
        payload = JSON.parse(customAlertJson);
      }
      const res = await fetch(`${apiBase}/investigation-planner/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const plan = await res.json();
        setGeneratedPlan(plan);
      } else {
        const errData = await res.json();
        setError(errData.detail || 'Plan generation failed');
      }
    } catch (err) {
      setError(err.message || 'Invalid JSON alert payload');
    } finally {
      setLoading(false);
    }
  };

  const copyJson = () => {
    if (generatedPlan) {
      navigator.clipboard.writeText(JSON.stringify(generatedPlan, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Top Header Card */}
      <div className="glass-panel" style={{ padding: '20px', background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(139, 92, 246, 0.08))', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', padding: '6px', borderRadius: '8px', display: 'flex' }}>
                <Sliders size={20} color="#fff" />
              </div>
              <h2 style={{ fontSize: '18px', fontWeight: '800', letterSpacing: '-0.01em', margin: 0 }}>
                FinSpectra Investigation Planner
              </h2>
              <span className="badge badge-medium" style={{ background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', color: '#34d399', fontSize: '11px' }}>
                12-Stage Deterministic Pipeline
              </span>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px', marginBottom: 0 }}>
              Generates structured, evidence-backed investigation plans with objective facts, red flags, taxonomy classification, information gaps, prioritized questions, evidence mapping, and conditional decision branching.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <div style={{ display: 'flex', background: 'rgba(0,0,0,0.3)', padding: '3px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              <button
                onClick={() => setPlannerMode('scenario')}
                style={{
                  background: plannerMode === 'scenario' ? 'var(--accent-indigo)' : 'transparent',
                  color: plannerMode === 'scenario' ? '#fff' : 'var(--text-secondary)',
                  border: 'none', padding: '5px 12px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', cursor: 'pointer'
                }}
              >
                Sample Scenarios (8)
              </button>
              <button
                onClick={() => setPlannerMode('custom')}
                style={{
                  background: plannerMode === 'custom' ? 'var(--accent-indigo)' : 'transparent',
                  color: plannerMode === 'custom' ? '#fff' : 'var(--text-secondary)',
                  border: 'none', padding: '5px 12px', borderRadius: '4px', fontSize: '11px', fontWeight: '600', cursor: 'pointer'
                }}
              >
                Custom Alert JSON
              </button>
            </div>

            <button
              className="btn-primary"
              onClick={() => runPlanner()}
              disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', borderRadius: '8px', color: '#fff', fontWeight: '700', fontSize: '12px', cursor: 'pointer', boxShadow: '0 0 15px rgba(99,102,241,0.4)' }}
            >
              <Play size={14} />
              {loading ? 'Running Pipeline...' : 'Generate Plan'}
            </button>
          </div>
        </div>

        {/* Scenario Selection Grid / Custom JSON area */}
        {plannerMode === 'scenario' ? (
          <div style={{ marginTop: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '8px' }}>
            {Object.entries(scenarios).map(([key, item]) => {
              const isSelected = selectedScenarioKey === key;
              return (
                <div
                  key={key}
                  onClick={() => handleSelectScenario(key)}
                  style={{
                    padding: '10px 14px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(99, 102, 241, 0.25)' : 'rgba(0, 0, 0, 0.25)',
                    border: isSelected ? '1px solid #818cf8' : '1px solid rgba(255,255,255,0.06)',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '8px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                    <span style={{ fontSize: '10px', fontWeight: '800', background: isSelected ? '#6366f1' : 'rgba(255,255,255,0.1)', color: '#fff', padding: '2px 6px', borderRadius: '4px' }}>
                      #{key}
                    </span>
                    <span style={{ fontSize: '12px', fontWeight: isSelected ? '700' : '500', color: isSelected ? '#fff' : 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.label}
                    </span>
                  </div>
                  {isSelected && <CheckCircle2 size={14} color="#818cf8" />}
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ marginTop: '16px' }}>
            <textarea
              value={customAlertJson}
              onChange={(e) => setCustomAlertJson(e.target.value)}
              rows={6}
              style={{
                width: '100%',
                background: 'rgba(0,0,0,0.4)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                color: '#34d399',
                fontFamily: 'monospace',
                fontSize: '12px',
                padding: '12px',
                boxSizing: 'border-box'
              }}
              placeholder='Enter RawAlertInput JSON...'
            />
          </div>
        )}
      </div>

      {error && (
        <div className="glass-panel" style={{ padding: '14px 18px', background: 'rgba(239, 68, 68, 0.1)', borderLeft: '4px solid #ef4444', color: '#fca5a5', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle size={16} color="#ef4444" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Plan Display */}
      {generatedPlan && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Plan Section Sub-navigation */}
          <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', background: 'rgba(0,0,0,0.3)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            {[
              { id: 'summary', label: 'Case & Classification', icon: Shield },
              { id: 'facts', label: `Objective Facts (${generatedPlan.facts.length})`, icon: CheckSquare },
              { id: 'red_flags', label: `Red Flags (${generatedPlan.red_flags.length})`, icon: AlertTriangle },
              { id: 'questions', label: `Questions (${generatedPlan.investigation_questions.length})`, icon: Search },
              { id: 'evidence', label: `Evidence Requirements (${generatedPlan.evidence_requirements.length})`, icon: Database },
              { id: 'sequence', label: `Investigation Sequence (${generatedPlan.investigation_steps.length})`, icon: Layers },
              { id: 'decisions', label: `Decision Logic (${generatedPlan.decision_points.length})`, icon: Activity },
              { id: 'json', label: 'Raw Validated JSON', icon: Code },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeSection === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveSection(tab.id)}
                  style={{
                    background: isActive ? 'var(--accent-indigo)' : 'transparent',
                    color: isActive ? '#fff' : 'var(--text-secondary)',
                    border: 'none',
                    padding: '8px 14px',
                    borderRadius: '6px',
                    fontSize: '11px',
                    fontWeight: '600',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    whiteSpace: 'nowrap',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Icon size={13} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Section: Summary / Case & Classification */}
          {activeSection === 'summary' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px' }}>
              {/* Classification Card */}
              <div className="glass-panel" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Alert Typology Classification
                  </span>
                  <span style={{ fontSize: '11px', background: 'rgba(99, 102, 241, 0.2)', border: '1px solid var(--accent-indigo)', color: '#a5b4fc', padding: '2px 8px', borderRadius: '4px', fontWeight: '700' }}>
                    {generatedPlan.classification.classification_status}
                  </span>
                </div>

                <div style={{ fontSize: '20px', fontWeight: '800', color: '#fff', marginBottom: '6px' }}>
                  {generatedPlan.classification.primary_category}
                </div>
                {generatedPlan.classification.subcategory && (
                  <div style={{ fontSize: '12px', color: 'var(--accent-cyan)', fontWeight: '600', marginBottom: '14px' }}>
                    Typology: {generatedPlan.classification.subcategory}
                  </div>
                )}

                {/* Confidence Bar */}
                <div style={{ marginBottom: '18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Confidence Score</span>
                    <span style={{ fontWeight: '700', color: '#34d399' }}>{Math.round(generatedPlan.classification.confidence * 100)}%</span>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.round(generatedPlan.classification.confidence * 100)}%`, height: '100%', background: 'linear-gradient(90deg, #6366f1, #34d399)', borderRadius: '3px' }} />
                  </div>
                </div>

                {/* Rationale Chain */}
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ fontSize: '11px', fontWeight: '700', color: '#a5b4fc', marginBottom: '8px', textTransform: 'uppercase' }}>
                    Evidence-Backed Classification Rationale
                  </div>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                    {generatedPlan.classification.rationale}
                  </pre>
                </div>
              </div>

              {/* Case Context Card */}
              <div className="glass-panel" style={{ padding: '20px' }}>
                <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Normalized Case Context
                </span>
                
                <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ background: 'rgba(0,0,0,0.25)', padding: '10px 14px', borderRadius: '6px', fontSize: '11px' }}>
                    <div style={{ color: 'var(--text-muted)' }}>Case ID / Alert ID</div>
                    <div style={{ fontWeight: '700', color: '#fff', marginTop: '2px' }}>{generatedPlan.case.case_id} &bull; {generatedPlan.case.alert_id}</div>
                  </div>

                  <div style={{ background: 'rgba(0,0,0,0.25)', padding: '10px 14px', borderRadius: '6px', fontSize: '11px' }}>
                    <div style={{ color: 'var(--text-muted)' }}>Alert Trigger</div>
                    <div style={{ fontWeight: '700', color: '#fff', marginTop: '2px' }}>{generatedPlan.case.alert_trigger.type || 'N/A'}</div>
                    <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>{generatedPlan.case.alert_trigger.reason || 'N/A'}</div>
                  </div>

                  <div style={{ background: 'rgba(0,0,0,0.25)', padding: '10px 14px', borderRadius: '6px', fontSize: '11px' }}>
                    <div style={{ color: 'var(--text-muted)' }}>Geographic Information</div>
                    <div style={{ fontWeight: '600', color: '#fff', marginTop: '2px' }}>
                      Origin: <strong>{generatedPlan.case.geographic_information.origin || 'UNKNOWN'}</strong> &rarr; Destination: <strong>{generatedPlan.case.geographic_information.destination || 'UNKNOWN'}</strong>
                    </div>
                  </div>

                  <div style={{ background: 'rgba(0,0,0,0.25)', padding: '10px 14px', borderRadius: '6px', fontSize: '11px' }}>
                    <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Information Gaps ({generatedPlan.information_gaps.length})</div>
                    <ul style={{ margin: 0, paddingLeft: '16px', color: '#fbbf24', fontSize: '11px' }}>
                      {generatedPlan.information_gaps.slice(0, 3).map((gap) => (
                        <li key={gap.gap_id} style={{ marginBottom: '3px' }}>
                          [{gap.gap_id}] {gap.description}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Section: Facts */}
          {activeSection === 'facts' && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckSquare size={16} color="var(--accent-cyan)" />
                  Objective Extracted Facts ({generatedPlan.facts.length})
                </h3>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Separated from interpretation; strictly sourced</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {generatedPlan.facts.map((fact) => (
                  <div key={fact.fact_id} style={{ padding: '12px 16px', borderRadius: '8px', background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ fontSize: '10px', fontWeight: '800', background: 'rgba(6, 182, 212, 0.2)', color: 'var(--accent-cyan)', padding: '2px 6px', borderRadius: '4px', marginRight: '8px' }}>
                        {fact.fact_id}
                      </span>
                      <span style={{ fontSize: '13px', fontWeight: '600', color: '#fff' }}>
                        {fact.statement}
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                      Source: <code>{fact.source}</code>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section: Red Flags */}
          {activeSection === 'red_flags' && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertTriangle size={16} color="var(--accent-amber)" />
                  Identified Red Flags & Anomalies ({generatedPlan.red_flags.length})
                </h3>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Grounded in objective facts</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '12px' }}>
                {generatedPlan.red_flags.map((rf) => (
                  <div key={rf.red_flag_id} style={{ padding: '16px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', fontWeight: '800', background: rf.severity === 'HIGH' ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.2)', color: rf.severity === 'HIGH' ? '#f87171' : '#fbbf24', padding: '2px 8px', borderRadius: '4px' }}>
                        {rf.red_flag_id} &bull; {rf.severity}
                      </span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        Confidence: <strong>{Math.round(rf.confidence * 100)}%</strong>
                      </span>
                    </div>

                    <div style={{ fontSize: '13px', fontWeight: '700', color: '#fff' }}>
                      {rf.description}
                    </div>

                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                      {rf.rationale}
                    </div>

                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '8px 10px', borderRadius: '6px', fontSize: '10px', color: 'var(--text-muted)' }}>
                      <div>Observed: <strong style={{ color: '#fff' }}>{String(rf.observed_value || 'N/A')}</strong></div>
                      <div>Baseline: <span>{rf.comparison_baseline || 'UNKNOWN'}</span></div>
                      <div style={{ marginTop: '4px', color: 'var(--accent-cyan)' }}>
                        Evidence Refs: <code>{rf.evidence_refs.join(', ')}</code>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section: Questions */}
          {activeSection === 'questions' && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Search size={16} color="var(--accent-indigo)" />
                  Prioritized Actionable Investigation Questions ({generatedPlan.investigation_questions.length})
                </h3>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Ranked by investigative impact & urgency</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {generatedPlan.investigation_questions.map((q, idx) => (
                  <div key={q.question_id} style={{ padding: '14px 18px', borderRadius: '8px', background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                      <span style={{ fontSize: '11px', fontWeight: '800', background: q.priority === 'HIGH' ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.2)', color: q.priority === 'HIGH' ? '#f87171' : '#fbbf24', padding: '3px 8px', borderRadius: '4px', whiteSpace: 'nowrap' }}>
                        {q.question_id} &bull; {q.priority}
                      </span>
                      <div>
                        <div style={{ fontSize: '13px', fontWeight: '700', color: '#fff', marginBottom: '4px' }}>
                          {q.question}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                          <strong>Objective:</strong> {q.objective}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', whiteSpace: 'nowrap' }}>
                      <span style={{ fontSize: '10px', background: 'rgba(255,255,255,0.08)', color: 'var(--text-muted)', padding: '2px 6px', borderRadius: '4px' }}>
                        Type: {q.expected_answer_type}
                      </span>
                      {q.related_red_flags.length > 0 && (
                        <span style={{ fontSize: '10px', color: 'var(--accent-amber)' }}>
                          Refs: {q.related_red_flags.join(', ')}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section: Evidence */}
          {activeSection === 'evidence' && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Database size={16} color="var(--accent-cyan)" />
                  Evidence Requirements Mapping ({generatedPlan.evidence_requirements.length})
                </h3>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Required data assets to answer questions</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '12px' }}>
                {generatedPlan.evidence_requirements.map((ev) => (
                  <div key={ev.evidence_id} style={{ padding: '14px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '800', background: 'rgba(6, 182, 212, 0.2)', color: 'var(--accent-cyan)', padding: '2px 6px', borderRadius: '4px' }}>
                        {ev.evidence_id} &bull; {ev.evidence_type}
                      </span>
                      <span style={{ fontSize: '10px', background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)', padding: '2px 6px', borderRadius: '4px' }}>
                        {ev.availability}
                      </span>
                    </div>

                    <div style={{ fontSize: '12px', fontWeight: '700', color: '#fff', marginBottom: '4px' }}>
                      {ev.description}
                    </div>

                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                      <strong>Why:</strong> {ev.why_required}
                    </div>

                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                      <span>Source: <code>{ev.source_category}</code></span>
                      <span>Questions: <code>{ev.related_question_ids.join(', ')}</code></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section: Investigation Sequence */}
          {activeSection === 'sequence' && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Layers size={16} color="var(--accent-indigo)" />
                  Ordered Investigation Sequence ({generatedPlan.investigation_steps.length} Steps)
                </h3>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Dependency-linked chronological workflow</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {generatedPlan.investigation_steps.map((step, idx) => (
                  <div key={step.step_id} style={{ display: 'flex', gap: '16px', alignItems: 'stretch' }}>
                    {/* Step number pillar */}
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '40px' }}>
                      <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '800', fontSize: '12px' }}>
                        {step.order}
                      </div>
                      {idx < generatedPlan.investigation_steps.length - 1 && (
                        <div style={{ width: '2px', flex: 1, background: 'rgba(99, 102, 241, 0.3)', margin: '4px 0' }} />
                      )}
                    </div>

                    {/* Step card */}
                    <div style={{ flex: 1, padding: '14px 18px', borderRadius: '8px', background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <span style={{ fontSize: '12px', fontWeight: '800', color: '#a5b4fc' }}>
                          {step.step_id} &bull; {step.objective}
                        </span>
                        <span style={{ fontSize: '10px', background: step.priority === 'HIGH' ? 'rgba(239,68,68,0.2)' : 'rgba(245,158,11,0.2)', color: step.priority === 'HIGH' ? '#f87171' : '#fbbf24', padding: '2px 6px', borderRadius: '4px', fontWeight: '700' }}>
                          {step.priority} Priority
                        </span>
                      </div>

                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        <strong>Rationale:</strong> {step.rationale}
                      </div>

                      <div style={{ display: 'flex', gap: '12px', fontSize: '10px', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                        <span>Questions: <code>{step.question_ids.join(', ')}</code></span>
                        <span>Evidence: <code>{step.required_evidence.join(', ')}</code></span>
                        <span>Dependencies: <code>{step.dependency.length > 0 ? step.dependency.join(', ') : 'None (Root Step)'}</code></span>
                        <span>Expected Output: <code>{step.expected_output}</code></span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section: Decision Logic */}
          {activeSection === 'decisions' && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Activity size={16} color="#34d399" />
                  Conditional Decision Points ({generatedPlan.decision_points.length})
                </h3>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Structured branching logic for orchestration engine</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: '14px' }}>
                {generatedPlan.decision_points.map((dec) => (
                  <div key={dec.decision_id} style={{ padding: '16px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', fontWeight: '800', color: '#34d399', background: 'rgba(16,185,129,0.15)', padding: '2px 8px', borderRadius: '4px' }}>
                        {dec.decision_id} &bull; After {dec.after_step}
                      </span>
                    </div>

                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '6px', fontSize: '11px', fontFamily: 'monospace', color: '#a5b4fc' }}>
                      Condition: <strong>{dec.condition}</strong>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      <div style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', padding: '8px 10px', borderRadius: '6px', fontSize: '11px' }}>
                        <div style={{ color: '#34d399', fontWeight: '700', fontSize: '10px' }}>IF TRUE &rarr;</div>
                        <code style={{ color: '#fff' }}>{dec.if_true}</code>
                      </div>
                      <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', padding: '8px 10px', borderRadius: '6px', fontSize: '11px' }}>
                        <div style={{ color: '#f87171', fontWeight: '700', fontSize: '10px' }}>IF FALSE &rarr;</div>
                        <code style={{ color: '#fff' }}>{dec.if_false}</code>
                      </div>
                    </div>

                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                      {dec.reason}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section: Raw JSON */}
          {activeSection === 'json' && (
            <div className="glass-panel" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: '700', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Code size={16} color="var(--accent-cyan)" />
                  Raw Validated InvestigationPlan JSON (v{generatedPlan.plan_version})
                </h3>
                <button
                  onClick={copyJson}
                  style={{
                    background: copied ? '#10b981' : 'var(--accent-indigo)',
                    color: '#fff',
                    border: 'none',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    fontSize: '11px',
                    fontWeight: '700',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                >
                  {copied ? 'Copied to Clipboard!' : 'Copy Plan JSON'}
                </button>
              </div>

              <pre style={{ margin: 0, background: 'rgba(0,0,0,0.5)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)', color: '#34d399', fontFamily: 'monospace', fontSize: '11px', maxHeight: '550px', overflowY: 'auto' }}>
                {JSON.stringify(generatedPlan, null, 2)}
              </pre>
            </div>
          )}

        </div>
      )}

    </div>
  );
}
