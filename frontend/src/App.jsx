import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  BrainCircuit,
  FileText,
  Network,
  Activity,
  Upload,
  Play,
  CheckCircle2,
  AlertTriangle,
  FileDown,
  RefreshCw,
  Search,
  ChevronRight,
  Database,
  Layers,
  User,
  Clock,
  Filter,
  Info,
  Globe,
  Shield,
  Zap,
  Server,
  Code,
  Cpu,
  Terminal,
  Sliders,
  CheckSquare,
  ArrowRight,
  Eye
} from 'lucide-react';
import InvestigationPlannerView from './InvestigationPlannerView';

const API_BASE = typeof window !== 'undefined' && window.location.origin.includes('5173') ? 'http://localhost:8000/api' : '/api';


const SYSTEM_AGENTS_META = {
  detection_agent: {
    agent_id: 'detection_agent',
    name: 'Isolation Forest & Threat Detector Agent',
    role: 'ML Anomaly Detection & Threat Intel IP Correlation',
    description: 'Scans transaction streams and WAF evidence logs using Isolation Forest model and correlates source IPs against threat intelligence databases.',
    logic: `def detect_anomalies(transactions, threat_ips):\n    features = extract_features(transactions) # amount, time_delta, velocity\n    scores = isolation_forest_model.decision_function(features)\n    threat_matches = [t for t in transactions if t.src_ip in threat_ips]\n    priority = "CRITICAL" if threat_matches else ("HIGH" if scores < -0.2 else "MEDIUM")\n    return Alert(anomaly_score=score, initial_priority=priority, signals=threat_matches)`
  },
  invest_planner: {
    agent_id: 'invest_planner',
    name: 'Planner Agent (invest.planner)',
    role: 'Investigation Objective & Plan Generator (Reusable Node)',
    description: 'Constructs structured, deterministic investigation plans based on alert rule signals (Structuring, Circular, Layering, Mule) and initial transaction context.',
    logic: `def invest_planner(state: InvestigationState):\n    signals = _select_primary_signals(alert, rule_signals)\n    base_steps = _build_baseline_steps() # GATHER_TXN, RESOLVE_ENTITIES, BUILD_GRAPH\n    domain_steps = _build_domain_steps(signals) # STRUCTURING, CIRCULAR, LAYERING\n    synthesis_steps = _build_synthesis_steps()\n    return InvestigationPlan(objective=..., steps=base_steps + domain_steps + synthesis_steps)`
  },
  hypothesis_generation: {
    agent_id: 'hypothesis_generation',
    name: 'Hypothesis Agent',
    role: 'AML & Threat Hypothesis Formulation',
    description: 'Formulates testable financial crime hypotheses (Structuring, Circular transfers, Mule network, Pass-through layering) linked to specific plan steps.',
    logic: `ACTION_HYPOTHESIS_MAP = {\n    ANALYZE_AMOUNT_PATTERNS: [\n        {"statement": "Account may be structuring transactions below reporting threshold", "typology": "STRUCTURING_SMURFING"}\n    ],\n    DETECT_GRAPH_CYCLES: [\n        {"statement": "Funds flowing in a circular pattern among connected accounts", "typology": "CIRCULAR_TRANSFER"}\n    ]\n}`
  },
  evidence_retrieval: {
    agent_id: 'evidence_retrieval',
    name: 'Evidence Retrieval Agent (Tool Dispatcher)',
    role: 'Automated Tool Execution & Empirical Data Gathering',
    description: 'Dispatches tool calls to DB_QUERY, GRAPH_QUERY (NetworkX cycles & centrality), and TYPOLOGY_MATCH engines to gather empirical evidence items.',
    logic: `def evidence_retrieval(state: InvestigationState):\n    for step in plan.steps:\n        if step.preferred_tool == ToolPreference.DB_QUERY:\n            ev = db_query_tool.run(account_id)\n        elif step.preferred_tool == ToolPreference.GRAPH_QUERY:\n            ev = graph_query_tool.run_cycles(graph)\n        elif step.preferred_tool == ToolPreference.TYPOLOGY_MATCH:\n            ev = typology_tool.match_rules(transactions)\n        state.evidence.append(ev)`
  },
  analysis_reasoning: {
    agent_id: 'analysis_reasoning',
    name: 'Analysis & Composite Risk Agent',
    role: 'Multi-Dimensional Risk Weighting & Finding Synthesis',
    description: 'Synthesizes evidence into findings and evaluates composite risk across Transaction, Network, Typology, and Customer risk dimensions.',
    logic: `def analysis_reasoning(state: InvestigationState):\n    txn_risk = calc_transaction_risk(state.evidence)\n    net_risk = calc_network_risk(state.evidence)\n    typ_risk = calc_typology_risk(state.evidence)\n    composite = 0.35*txn_risk + 0.25*net_risk + 0.25*typ_risk + 0.15*customer_risk\n    risk_level = "CRITICAL" if composite >= 0.85 else ("HIGH" if composite >= 0.70 else "MEDIUM")\n    return AnalysisResult(composite_risk_score=composite, risk_level=risk_level)`
  },
  adaptive_planner: {
    agent_id: 'adaptive_planner',
    name: 'Adaptive Router Agent (Loop Guard)',
    role: 'Evidence Sufficiency Evaluation & Re-plan Guard',
    description: 'Evaluates evidence sufficiency score and confidence thresholds. Decides whether to STOP and proceed to decision, or REPLAN for additional evidence.',
    logic: `def adaptive_planner(state: InvestigationState):\n    sufficiency = calc_evidence_sufficiency(state.evidence)\n    if sufficiency >= 0.60 or state.iteration_count >= state.max_iterations:\n        return AdaptivePlannerDecision.STOP\n    return AdaptivePlannerDecision.REPLAN`
  },
  decision_node: {
    agent_id: 'decision_node',
    name: 'Policy Decision Matrix Agent',
    role: 'Deterministic Policy Matrix Evaluator (Policy v1.0)',
    description: 'Applies regulatory decision matrix rules to produce final outcomes: SAR_RECOMMENDED, ESCALATE, MONITOR, CLEAR, or HUMAN_REVIEW.',
    logic: `def decision_node(state: InvestigationState):\n    # Policy Matrix v1.0\n    if state.analysis.risk_level == "CRITICAL" or has_threat_intel_match(state):\n        outcome = DecisionOutcome.SAR_RECOMMENDED\n        action = "File Suspicious Activity Report with FIU within 24 hours"\n    elif state.analysis.risk_level == "HIGH":\n        outcome = DecisionOutcome.ESCALATE\n    return InvestigationDecision(outcome=outcome, policy_version="1.0")`
  },
  report_generation: {
    agent_id: 'report_generation',
    name: 'Regulatory Report & PDF Agent',
    role: 'Report Narrative Synthesis & ReportLab PDF Compiler',
    description: 'Compiles full investigation narrative, network findings topology graph, evidence audit log, and renders downloadable ReportLab PDF.',
    logic: `def report_generation(state: InvestigationState):\n    report_data = build_report_data(state)\n    pdf_path = render_reportlab_pdf(report_data)\n    return {"report_data": report_data, "pdf_path": pdf_path}`
  }
};

export default function App() {
  const [activeTab, setActiveTab] = useState('alerts'); // 'alerts', 'investigation', 'agent-inspector', 'database', 'audit'
  const [metrics, setMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [currentInvestigation, setCurrentInvestigation] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [agentExecutionData, setAgentExecutionData] = useState(null);
  const [selectedAgentKey, setSelectedAgentKey] = useState('invest_planner');
  const [inspectorSubTab, setInspectorSubTab] = useState('overview'); // 'overview', 'logic', 'payload', 'tools', 'audit'
  const [loading, setLoading] = useState(false);
  const [investigating, setInvestigating] = useState(false);
  const [authToken, setAuthToken] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [priorityFilter, setPriorityFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Authenticate dev user on load
  useEffect(() => {
    loginDevUser();
  }, []);

  useEffect(() => {
    if (authToken) {
      fetchDashboardMetrics();
      fetchAlerts();
      fetchAgentExecution('latest');
    }
  }, [authToken]);

  const loginDevUser = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'investigator@finspectra.dev', password: 'finspectra_investigator' })
      });
      if (res.ok) {
        const data = await res.json();
        setAuthToken(data.access_token);
      } else {
        const adminRes = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: 'admin@finspectra.dev', password: 'finspectra_admin' })
        });
        if (adminRes.ok) {
          const data = await adminRes.json();
          setAuthToken(data.access_token);
        }
      }
    } catch (e) {
      console.error("Auth failed:", e);
    }
  };

  const getHeaders = () => ({
    'Authorization': `Bearer ${authToken}`,
    'Content-Type': 'application/json'
  });

  const fetchDashboardMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/summary`, { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setMetrics(data.metrics);
      }
    } catch (e) {
      console.error("Failed to fetch metrics", e);
    }
  };

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/alerts?page_size=100`, { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        const items = data.items || [];
        setAlerts(items);
        if (items.length > 0 && !selectedAlert) {
          setSelectedAlert(items[0]);
        }
      }
    } catch (e) {
      console.error("Failed to fetch alerts", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchAgentExecution = async (invId = 'latest') => {
    try {
      const targetId = invId || 'latest';
      const res = await fetch(`${API_BASE}/investigations/${targetId}/agent-execution`, { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setAgentExecutionData(data);
      }
    } catch (e) {
      console.error("Failed to fetch agent execution", e);
    }
  };


  const triggerDetection = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/transactions/detect`, {
        method: 'POST',
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setUploadStatus(`Detection pipeline complete: ${data.alerts_created} alerts created across ${data.total_transactions_analyzed} events.`);
        fetchAlerts();
        fetchDashboardMetrics();
      }
    } catch (e) {
      setUploadStatus(`Detection error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSeedRealDatasets = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/dashboard/seed-demo`, {
        method: 'POST',
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setUploadStatus(`Real Evidence & Threat Datasets ingested! ${data.detection.alerts_created} High/Critical alerts ready for investigation.`);
        fetchAlerts();
        fetchDashboardMetrics();
      }
    } catch (e) {
      setUploadStatus(`Seed error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e, endpoint = 'upload-and-detect') => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/transactions/${endpoint}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` },
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        const accepted = data.ingestion ? data.ingestion.accepted_rows : 0;
        const alertsCreated = data.detection ? data.detection.alerts_created : 0;
        setUploadStatus(`Dataset accepted: ${accepted} records ingested. Created ${alertsCreated} prioritized alerts.`);
        fetchAlerts();
        fetchDashboardMetrics();
      }
    } catch (err) {
      setUploadStatus(`Upload failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const startInvestigation = async (alertId) => {
    setInvestigating(true);
    try {
      const createRes = await fetch(`${API_BASE}/investigations`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ alert_id: alertId })
      });
      
      let invId;
      if (createRes.ok) {
        const inv = await createRes.json();
        invId = inv.id;
      } else if (createRes.status === 409) {
        const listRes = await fetch(`${API_BASE}/investigations`, { headers: getHeaders() });
        const list = await listRes.json();
        const existing = list.find(i => i.alert_id === alertId);
        if (existing) invId = existing.id;
      }

      if (invId) {
        const runRes = await fetch(`${API_BASE}/investigations/${invId}/run`, {
          method: 'POST',
          headers: getHeaders()
        });

        if (runRes.ok) {
          const detailRes = await fetch(`${API_BASE}/investigations/${invId}`, { headers: getHeaders() });
          const detail = await detailRes.json();
          setCurrentInvestigation(detail);

          const graphRes = await fetch(`${API_BASE}/investigations/${invId}/graph`, { headers: getHeaders() });
          if (graphRes.ok) setGraphData(await graphRes.json());

          const reportRes = await fetch(`${API_BASE}/investigations/${invId}/report`, { headers: getHeaders() });
          if (reportRes.ok) setReportData(await reportRes.json());

          await fetchAgentExecution(invId);

          setActiveTab('investigation');
          fetchDashboardMetrics();
        }
      }
    } catch (e) {
      console.error("Investigation failed", e);
    } finally {
      setInvestigating(false);
    }
  };

  const filteredAlerts = alerts.filter(alert => {
    if (priorityFilter !== 'ALL' && alert.initial_priority !== priorityFilter) {
      return false;
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchReason = alert.reasons && alert.reasons.some(r => r.toLowerCase().includes(q));
      const matchId = alert.id.toLowerCase().includes(q);
      const matchTxn = alert.transaction_id.toLowerCase().includes(q);
      return matchReason || matchId || matchTxn;
    }
    return true;
  });

  const selectedAgentMeta = SYSTEM_AGENTS_META[selectedAgentKey] || SYSTEM_AGENTS_META.invest_planner;
  const currentAgentExecution = agentExecutionData && agentExecutionData.agents ? agentExecutionData.agents[selectedAgentKey] : null;

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      {/* Header Bar */}
      <header style={{ borderBottom: '1px solid var(--border-color)', background: 'rgba(11, 15, 25, 0.85)', backdropFilter: 'blur(16px)', position: 'sticky', top: 0, zIndex: 50, padding: '12px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', maxWidth: '1440px', margin: '0 auto' }}>
          
          {/* Logo & Platform Name */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', padding: '8px', borderRadius: '10px', display: 'flex', boxShadow: '0 0 15px rgba(99, 102, 241, 0.4)' }}>
              <ShieldAlert size={26} color="#ffffff" />
            </div>
            <div>
              <h1 style={{ fontSize: '18px', fontWeight: '800', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '8px' }}>
                FinSpectra
                <span className="badge badge-medium" style={{ fontSize: '10px', background: 'rgba(99, 102, 241, 0.2)', border: '1px solid var(--accent-indigo)', color: 'var(--accent-indigo-light)' }}>
                  v1.0.0 Multi-Agent Inspector
                </span>
              </h1>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Financial Crime & Threat Intelligence Autonomous Multi-Agent System</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div style={{ display: 'flex', gap: '6px', background: 'rgba(255,255,255,0.03)', padding: '4px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
            <button
              onClick={() => setActiveTab('alerts')}
              style={{
                background: activeTab === 'alerts' ? 'var(--accent-indigo)' : 'transparent',
                color: activeTab === 'alerts' ? '#fff' : 'var(--text-secondary)',
                border: 'none', padding: '7px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', transition: 'all 0.2s'
              }}
            >
              <AlertTriangle size={14} /> Alert Queue ({alerts.length})
            </button>

            <button
              onClick={() => setActiveTab('investigation')}
              style={{
                background: activeTab === 'investigation' ? 'var(--accent-indigo)' : 'transparent',
                color: activeTab === 'investigation' ? '#fff' : 'var(--text-secondary)',
                border: 'none', padding: '7px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', transition: 'all 0.2s'
              }}
            >
              <BrainCircuit size={14} /> Autonomous Case Console {currentInvestigation && <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }}></span>}
            </button>

            <button
              onClick={() => {
                setActiveTab('agent-inspector');
                if (currentInvestigation && !agentExecutionData) {
                  fetchAgentExecution(currentInvestigation.id);
                }
              }}
              style={{
                background: activeTab === 'agent-inspector' ? 'var(--accent-indigo)' : 'transparent',
                color: activeTab === 'agent-inspector' ? '#fff' : 'var(--text-secondary)',
                border: 'none', padding: '7px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', transition: 'all 0.2s'
              }}
            >
              <Layers size={14} /> Multi-Agent Working Inspector
            </button>

            <button
              onClick={() => setActiveTab('planner')}
              style={{
                background: activeTab === 'planner' ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'transparent',
                color: activeTab === 'planner' ? '#fff' : 'var(--text-secondary)',
                border: activeTab === 'planner' ? '1px solid #a5b4fc' : 'none',
                padding: '7px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: '700', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', transition: 'all 0.2s', boxShadow: activeTab === 'planner' ? '0 0 12px rgba(99, 102, 241, 0.4)' : 'none'
              }}
            >
              <Sliders size={14} /> Investigation Planner
            </button>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button className="btn-primary" onClick={triggerDetection} disabled={loading}>
              <Play size={14} /> {loading ? 'Running Engine...' : 'Run Detection'}
            </button>
          </div>

        </div>
      </header>

      {/* Main Container */}
      <main style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px' }}>

        {/* Upload/Status Banner */}
        {uploadStatus && (
          <div className="glass-panel" style={{ padding: '12px 18px', marginBottom: '20px', borderLeft: '4px solid var(--accent-cyan)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(6, 182, 212, 0.1)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
              <CheckCircle2 size={16} color="var(--accent-cyan)" />
              <span>{uploadStatus}</span>
            </div>
            <button onClick={() => setUploadStatus(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '14px' }}>✕</button>
          </div>
        )}

        {/* KPI Dashboard Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px', marginBottom: '24px' }}>
          <div className="glass-panel" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>
              WAF Evidence Logs <span>Real Logs</span>
            </div>
            <div style={{ fontSize: '26px', fontWeight: '800', marginTop: '6px', color: 'var(--accent-cyan)' }}>
              {metrics ? (metrics.evidence_logs_count || 0) : '282'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Server size={12} /> Suspicious Web Traffic
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>
              Threat Intelligence IPs <span>IP Abuse DB</span>
            </div>
            <div style={{ fontSize: '26px', fontWeight: '800', marginTop: '6px', color: 'var(--accent-rose)' }}>
              {metrics ? (metrics.threat_intel_count || 0) : '56'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--accent-rose)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Shield size={12} /> 100% Critical Abuse Score
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>
              Open Alerts <span>Isolation Forest</span>
            </div>
            <div style={{ fontSize: '26px', fontWeight: '800', marginTop: '6px', color: 'var(--accent-amber)' }}>
              {metrics ? metrics.open_alerts : alerts.length}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Score Threshold &ge; 0.50
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>
              System Agents <span>Connected</span>
            </div>
            <div style={{ fontSize: '26px', fontWeight: '800', marginTop: '6px', color: 'var(--accent-indigo-light)' }}>
              8 Active Agents
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Full Internal Working Visibility
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>
              Completed Cases <span>LangGraph</span>
            </div>
            <div style={{ fontSize: '26px', fontWeight: '800', marginTop: '6px', color: '#10b981' }}>
              {metrics ? metrics.completed_investigations : '0'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Full Traceability Chain
            </div>
          </div>
        </div>

        {/* Tab 1: Alert Queue & Prioritization */}
        {activeTab === 'alerts' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: '20px' }}>
            
            {/* Alert List */}
            <div className="glass-panel" style={{ padding: '20px' }}>
              
              {/* Header & Filter Controls */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
                <h2 style={{ fontSize: '16px', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertTriangle size={18} color="var(--accent-amber)" />
                  Prioritized Threat & Anomaly Alert Queue ({filteredAlerts.length})
                </h2>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ position: 'relative' }}>
                    <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                    <input
                      type="text"
                      placeholder="Search IP, Country, Rule..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      style={{
                        background: 'rgba(0,0,0,0.3)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '6px',
                        padding: '6px 12px 6px 30px',
                        fontSize: '11px',
                        color: 'var(--text-primary)',
                        outline: 'none',
                        width: '180px'
                      }}
                    />
                  </div>

                  <button onClick={fetchAlerts} className="btn-secondary" style={{ padding: '6px 10px', fontSize: '11px' }}>
                    <RefreshCw size={12} /> Refresh
                  </button>
                </div>
              </div>

              {/* Priority Pills */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(p => (
                  <button
                    key={p}
                    onClick={() => setPriorityFilter(p)}
                    style={{
                      background: priorityFilter === p ? 'var(--accent-indigo)' : 'rgba(255,255,255,0.03)',
                      color: priorityFilter === p ? '#fff' : 'var(--text-muted)',
                      border: '1px solid var(--border-color)',
                      padding: '4px 10px',
                      borderRadius: '12px',
                      fontSize: '11px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>

              {filteredAlerts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '50px 20px', color: 'var(--text-muted)' }}>
                  <Activity size={36} style={{ marginBottom: '12px', opacity: 0.4 }} />
                  <p style={{ fontSize: '13px' }}>No alerts matched filter. Click <strong>Seed Real Datasets</strong> or <strong>Run Detection</strong> above.</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '600px', overflowY: 'auto', paddingRight: '4px' }}>
                  {filteredAlerts.map((alert) => {
                    const isSelected = selectedAlert && selectedAlert.id === alert.id;
                    const priorityClass = `badge-${alert.initial_priority.toLowerCase()}`;
                    const hasThreatMatch = alert.rule_signals && alert.rule_signals.some(s => s.signal_type === 'CRITICAL_THREAT_INTEL_MATCH');

                    return (
                      <div
                        key={alert.id}
                        onClick={() => setSelectedAlert(alert)}
                        style={{
                          background: isSelected ? 'rgba(99, 102, 241, 0.14)' : 'rgba(255,255,255,0.02)',
                          border: isSelected ? '1px solid var(--accent-indigo)' : '1px solid rgba(255,255,255,0.06)',
                          borderRadius: '8px',
                          padding: '14px',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span className={`badge ${priorityClass}`}>{alert.initial_priority}</span>
                            {hasThreatMatch && (
                              <span className="badge badge-sar" style={{ fontSize: '10px' }}>THREAT IP MATCH</span>
                            )}
                            <span style={{ fontSize: '12px', fontWeight: '700', fontFamily: 'monospace' }}>Alert #{alert.id.substring(0, 8)}</span>
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--accent-cyan)', fontWeight: '700' }}>
                            Score: {(alert.anomaly_score * 100).toFixed(1)}%
                          </div>
                        </div>

                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: '1.4' }}>
                          {alert.reasons && alert.reasons.length > 0 ? alert.reasons[0] : 'Suspicious activity detected'}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
                          <span>Signals: {alert.rule_signals ? alert.rule_signals.length : 0} triggered</span>
                          <button
                            onClick={(e) => { e.stopPropagation(); startInvestigation(alert.id); }}
                            className="btn-primary"
                            style={{ padding: '4px 12px', fontSize: '11px' }}
                            disabled={investigating}
                          >
                            <BrainCircuit size={12} /> {investigating ? 'Analyzing...' : 'Investigate Case'}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Selected Alert Sidebar */}
            <div className="glass-panel" style={{ padding: '20px', height: 'fit-content' }}>
              {selectedAlert ? (
                <div>
                  <h3 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '14px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Info size={16} color="var(--accent-indigo)" /> Selected Alert Details
                  </h3>

                  <div style={{ background: 'rgba(0,0,0,0.3)', padding: '14px', borderRadius: '8px', marginBottom: '16px', fontSize: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Alert ID:</span>
                      <span style={{ fontFamily: 'monospace', fontWeight: '600' }}>{selectedAlert.id}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Event Record ID:</span>
                      <span style={{ fontFamily: 'monospace' }}>{selectedAlert.transaction_id.substring(0, 14)}...</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Anomaly Score:</span>
                      <span style={{ color: 'var(--accent-amber)', fontWeight: '700' }}>{selectedAlert.anomaly_score.toFixed(4)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Priority & Status:</span>
                      <span><span className={`badge badge-${selectedAlert.initial_priority.toLowerCase()}`}>{selectedAlert.initial_priority}</span> {selectedAlert.status}</span>
                    </div>
                  </div>

                  <h4 style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                    Threat & Anomaly Signals ({selectedAlert.rule_signals ? selectedAlert.rule_signals.length : 0})
                  </h4>
                  
                  {selectedAlert.rule_signals && selectedAlert.rule_signals.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '18px' }}>
                      {selectedAlert.rule_signals.map((sig, i) => (
                        <div key={i} style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '6px', fontSize: '11px', borderLeft: sig.signal_type.includes('THREAT') ? '3px solid var(--accent-rose)' : '3px solid var(--accent-indigo)' }}>
                          <div style={{ fontWeight: '700', color: sig.signal_type.includes('THREAT') ? 'var(--accent-rose)' : 'var(--accent-indigo-light)' }}>
                            {sig.signal_type}
                          </div>
                          <div style={{ color: 'var(--text-muted)', marginTop: '4px', lineHeight: '1.3' }}>{sig.reason}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '16px' }}>Statistical anomaly detected by Isolation Forest model.</p>
                  )}

                  <button
                    onClick={() => startInvestigation(selectedAlert.id)}
                    className="btn-primary"
                    style={{ width: '100%', justifyContent: 'center', padding: '10px' }}
                    disabled={investigating}
                  >
                    <Play size={14} /> Launch LangGraph Autonomous Case Workflow
                  </button>
                </div>
              ) : (
                <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '30px 10px' }}>
                  Select an alert from the queue
                </div>
              )}
            </div>

          </div>
        )}

        {/* Tab 2: Autonomous Case Console (LangGraph Workflow) */}
        {activeTab === 'investigation' && (
          <div>
            {!currentInvestigation ? (
              <div className="glass-panel" style={{ padding: '50px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                <BrainCircuit size={48} style={{ opacity: 0.4, marginBottom: '14px', color: 'var(--accent-indigo)' }} />
                <h3 style={{ fontSize: '16px', color: 'var(--text-primary)', marginBottom: '8px', fontWeight: '700' }}>No Active Case Selected</h3>
                <p style={{ fontSize: '13px', marginBottom: '20px' }}>Select any alert from the <strong>Alert Queue</strong> and click <strong>Investigate Case</strong> to run the LangGraph workflow.</p>
                <button onClick={() => setActiveTab('alerts')} className="btn-primary">
                  Go to Alert Queue
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                {/* Case Header & Traceability Bar */}
                <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-indigo)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                        <h2 style={{ fontSize: '18px', fontWeight: '800' }}>Case #{currentInvestigation.id.substring(0, 8)}</h2>
                        <span className="badge badge-medium">{currentInvestigation.status}</span>
                        {currentInvestigation.decision && (
                          <span className={`badge ${currentInvestigation.decision.decision === 'SAR_RECOMMENDED' ? 'badge-sar' : 'badge-high'}`}>
                            {currentInvestigation.decision.decision}
                          </span>
                        )}
                      </div>
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        Alert ID: <span style={{ fontFamily: 'monospace' }}>{currentInvestigation.alert_id}</span> | LangGraph Thread: <span style={{ fontFamily: 'monospace' }}>thread_id={currentInvestigation.id}</span>
                      </p>
                    </div>

                    <div style={{ display: 'flex', gap: '10px' }}>
                      <button
                        onClick={() => {
                          setSelectedAgentKey('invest_planner');
                          setActiveTab('agent-inspector');
                        }}
                        className="btn-secondary"
                        style={{ border: '1px solid var(--accent-indigo)' }}
                      >
                        <Eye size={14} color="var(--accent-indigo-light)" /> Inspect Agent Internal Workings
                      </button>

                      {reportData && reportData.report_id && (
                        <a
                          href={`${API_BASE}/reports/${reportData.report_id}/download`}
                          target="_blank"
                          rel="noreferrer"
                          className="btn-primary"
                          style={{ textDecoration: 'none' }}
                        >
                          <FileDown size={14} /> Download PDF Regulatory Report
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Traceability Chain Display */}
                  <div style={{ marginTop: '16px', background: 'rgba(0,0,0,0.3)', padding: '10px 14px', borderRadius: '6px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px', overflowX: 'auto' }}>
                    <span style={{ fontWeight: '700', color: 'var(--accent-indigo-light)' }}>TRACEABILITY:</span>
                    <span>case_id</span> <ChevronRight size={12} />
                    <span style={{ color: 'var(--accent-cyan)' }}>plan_id</span> <ChevronRight size={12} />
                    <span>step_id</span> <ChevronRight size={12} />
                    <span style={{ color: 'var(--accent-amber)' }}>evidence_id ({currentInvestigation.evidence_items ? currentInvestigation.evidence_items.length : 0})</span> <ChevronRight size={12} />
                    <span style={{ color: 'var(--accent-rose)' }}>decision_id</span>
                  </div>
                </div>

                {/* LangGraph Reusable Node Visualizer */}
                <div className="glass-panel" style={{ padding: '20px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <BrainCircuit size={16} color="var(--accent-indigo)" />
                    LangGraph Multi-Agent Architecture Stepper (Click any card to inspect agent internals)
                  </h3>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '10px' }}>
                    {[
                      { key: 'invest_planner', title: 'invest.planner', type: 'PLANNER', desc: 'Structured Plan' },
                      { key: 'hypothesis_generation', title: 'Hypothesis', type: 'ANALYSIS', desc: 'Threat & AML' },
                      { key: 'evidence_retrieval', title: 'Evidence Tool', type: 'TOOL', desc: 'WAF & Threat Intel' },
                      { key: 'analysis_reasoning', title: 'Analysis', type: 'REASONING', desc: 'Composite Risk' },
                      { key: 'adaptive_planner', title: 'Adaptive Planner', type: 'ROUTER', desc: 'STOP / REPLAN' },
                      { key: 'decision_node', title: 'Decision Node', type: 'POLICY', desc: 'Policy Matrix v1.0' },
                      { key: 'report_generation', title: 'Report Agent', type: 'OUTPUT', desc: 'ReportLab PDF' }
                    ].map((step, idx) => (
                      <div
                        key={idx}
                        onClick={() => {
                          setSelectedAgentKey(step.key);
                          setActiveTab('agent-inspector');
                        }}
                        className="agent-node-card"
                        style={{ textAlign: 'center' }}
                      >
                        <div style={{ fontSize: '10px', color: 'var(--accent-indigo-light)', fontWeight: '600' }}>Step {idx + 1}</div>
                        <div style={{ fontSize: '12px', fontWeight: '700', margin: '4px 0' }}>{step.title}</div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{step.desc}</div>
                        <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', fontSize: '10px', color: '#10b981' }}>
                          <CheckCircle2 size={12} color="#10b981" /> Inspect Logic
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Evidence & Decision Matrix */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

                  {/* Evidence Items */}
                  <div className="glass-panel" style={{ padding: '20px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Layers size={16} color="var(--accent-cyan)" />
                      Correlated Evidence ({currentInvestigation.evidence_items ? currentInvestigation.evidence_items.length : 0})
                    </h3>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '350px', overflowY: 'auto' }}>
                      {currentInvestigation.evidence_items && currentInvestigation.evidence_items.map((ev, idx) => (
                        <div key={idx} style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '6px', fontSize: '11px', borderLeft: '3px solid var(--accent-cyan)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span style={{ fontWeight: '700', color: 'var(--accent-cyan)' }}>{ev.evidence_type}</span>
                            <span style={{ color: 'var(--text-muted)' }}>Source: {ev.source}</span>
                          </div>
                          <div style={{ color: 'var(--text-secondary)', lineHeight: '1.4' }}>{ev.description}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Decision & Policy Matrix */}
                  <div className="glass-panel" style={{ padding: '20px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <ShieldAlert size={16} color="var(--accent-rose)" />
                      Deterministic Decision Policy Outcome
                    </h3>

                    {currentInvestigation.decision ? (
                      <div>
                        <div style={{ background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '14px', borderRadius: '8px', marginBottom: '12px' }}>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Recommended Outcome</div>
                          <div style={{ fontSize: '22px', fontWeight: '800', color: 'var(--accent-rose)', marginTop: '2px' }}>
                            {currentInvestigation.decision.decision}
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                            Evaluated Risk Level: <strong>{currentInvestigation.decision.risk_level}</strong>
                          </div>
                        </div>

                        <h4 style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '6px' }}>Decision Rationale:</h4>
                        <ul style={{ fontSize: '11px', color: 'var(--text-secondary)', paddingLeft: '16px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {currentInvestigation.decision.reasons && currentInvestigation.decision.reasons.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>

                        {currentInvestigation.decision.required_human_action && (
                          <div style={{ marginTop: '12px', background: 'rgba(245, 158, 11, 0.1)', padding: '10px', borderRadius: '6px', fontSize: '11px', color: '#fcd34d' }}>
                            <strong>Required Human Action:</strong> {currentInvestigation.decision.required_human_action}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Decision pending workflow execution.</p>
                    )}
                  </div>

                </div>

                {/* Graph Visualization Section */}
                {graphData && (
                  <div className="glass-panel" style={{ padding: '20px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Network size={16} color="var(--accent-purple)" />
                      Correlated Entity & Threat Network Graph ({graphData.nodes ? graphData.nodes.length : 0} Nodes, {graphData.edges ? graphData.edges.length : 0} Edges)
                    </h3>

                    <div className="graph-container" style={{ padding: '20px', minHeight: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', justifyContent: 'center' }}>
                        {graphData.nodes && graphData.nodes.slice(0, 10).map((node, i) => (
                          <div key={i} style={{ background: 'rgba(99, 102, 241, 0.15)', border: '1px solid var(--accent-indigo)', padding: '8px 14px', borderRadius: '20px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: node.node_type === 'ACCOUNT' ? '#6366f1' : node.node_type === 'IP' ? '#ef4444' : '#f59e0b' }}></span>
                            <span>{node.label}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

              </div>
            )}
          </div>
        )}

        {/* Tab 3: Multi-Agent Working Inspector (NEW FEATURE) */}
        {activeTab === 'agent-inspector' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

            {/* Inspector Header */}
            <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-indigo)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: '800', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Layers size={20} color="var(--accent-indigo-light)" />
                    Multi-Agent Operations & Internal Working Inspector
                  </h2>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Inspect full internal workings, prompts, decision policies, tool dispatches, input/output state payloads, and audit logs for every agent in FinSpectra.
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {currentInvestigation && (
                    <button
                      onClick={() => fetchAgentExecution(currentInvestigation.id)}
                      className="btn-secondary"
                      style={{ fontSize: '11px', padding: '6px 12px' }}
                    >
                      <RefreshCw size={12} /> Refresh Case Payload
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Agent Topology Selector Grid */}
            <div className="glass-panel" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '13px', fontWeight: '700', marginBottom: '14px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                System Agents Topography (8 Agents Registered) — Select Agent to Inspect
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                {Object.keys(SYSTEM_AGENTS_META).map((agentKey) => {
                  const meta = SYSTEM_AGENTS_META[agentKey];
                  const exec = agentExecutionData && agentExecutionData.agents ? agentExecutionData.agents[agentKey] : null;
                  const isSelected = selectedAgentKey === agentKey;

                  return (
                    <div
                      key={agentKey}
                      onClick={() => setSelectedAgentKey(agentKey)}
                      className={`agent-node-card ${isSelected ? 'active' : ''}`}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <span style={{ fontSize: '11px', fontWeight: '700', color: isSelected ? 'var(--accent-indigo-light)' : 'var(--text-primary)' }}>
                          {meta.name}
                        </span>
                        <span className={`agent-status-dot ${exec && exec.status === 'COMPLETED' ? 'agent-status-completed' : 'agent-status-running'}`}></span>
                      </div>

                      <p style={{ fontSize: '10px', color: 'var(--text-muted)', lineHeight: '1.3', marginBottom: '8px' }}>
                        {meta.role}
                      </p>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '10px', color: 'var(--text-secondary)', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '6px' }}>
                        <span>Status: <strong style={{ color: '#10b981' }}>{exec ? exec.status : 'READY'}</strong></span>
                        <span style={{ color: 'var(--accent-indigo-light)' }}>Inspect &rarr;</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Detailed Agent Internal Inspector Drawer */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              
              {/* Agent Detail Header & Sub-nav */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <h3 style={{ fontSize: '18px', fontWeight: '800', color: 'var(--accent-indigo-light)' }}>
                      {selectedAgentMeta.name}
                    </h3>
                    <span className="badge badge-medium">{selectedAgentMeta.agent_id}</span>
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    {selectedAgentMeta.description}
                  </p>
                </div>

                {/* Sub-tab Pills */}
                <div style={{ display: 'flex', gap: '6px', background: 'rgba(0,0,0,0.3)', padding: '4px', borderRadius: '8px' }}>
                  {[
                    { key: 'overview', label: 'Overview', icon: Info },
                    { key: 'logic', label: 'Internal Logic & Policy Code', icon: Code },
                    { key: 'payload', label: 'Inputs & Outputs Payload', icon: Cpu },
                    { key: 'tools', label: 'Tool Dispatch', icon: Sliders },
                    { key: 'audit', label: 'Audit Log Stream', icon: Terminal }
                  ].map(tab => {
                    const IconComp = tab.icon;
                    return (
                      <button
                        key={tab.key}
                        onClick={() => setInspectorSubTab(tab.key)}
                        style={{
                          background: inspectorSubTab === tab.key ? 'var(--accent-indigo)' : 'transparent',
                          color: inspectorSubTab === tab.key ? '#fff' : 'var(--text-secondary)',
                          border: 'none',
                          padding: '6px 12px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: '600',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px'
                        }}
                      >
                        <IconComp size={12} /> {tab.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Sub-tab Content Viewers */}

              {/* 1. Overview */}
              {inspectorSubTab === 'overview' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                    <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--accent-cyan)', marginBottom: '10px' }}>
                      Agent Architecture Specs
                    </h4>
                    <div style={{ fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div><strong style={{ color: 'var(--text-muted)' }}>Agent Key:</strong> <code>{selectedAgentMeta.agent_id}</code></div>
                      <div><strong style={{ color: 'var(--text-muted)' }}>Execution Context:</strong> LangGraph StateGraph Node</div>
                      <div><strong style={{ color: 'var(--text-muted)' }}>Thread Isolation:</strong> <code>thread_id = case_id</code></div>
                      <div><strong style={{ color: 'var(--text-muted)' }}>Primary Role:</strong> {selectedAgentMeta.role}</div>
                      <div><strong style={{ color: 'var(--text-muted)' }}>State Input Dependency:</strong> InvestigationState dictionary</div>
                    </div>
                  </div>

                  <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                    <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--accent-amber)', marginBottom: '10px' }}>
                      Runtime Execution Metrics
                    </h4>
                    {currentAgentExecution ? (
                      <div style={{ fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div><strong style={{ color: 'var(--text-muted)' }}>Status:</strong> <span style={{ color: '#10b981', fontWeight: '700' }}>{currentAgentExecution.status}</span></div>
                        <div><strong style={{ color: 'var(--text-muted)' }}>Tools Dispatched:</strong> {currentAgentExecution.tool_calls ? currentAgentExecution.tool_calls.length : 0}</div>
                        <div><strong style={{ color: 'var(--text-muted)' }}>Audit Log Events:</strong> {currentAgentExecution.audit_events ? currentAgentExecution.audit_events.length : 0}</div>
                        <div><strong style={{ color: 'var(--text-muted)' }}>Target Case ID:</strong> <code>{agentExecutionData.investigation_id}</code></div>
                      </div>
                    ) : (
                      <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Run any investigation case from the Alert Queue to view live execution metrics.</p>
                    )}
                  </div>
                </div>
              )}

              {/* 2. Internal Logic & Policy Code */}
              {inspectorSubTab === 'logic' && (
                <div>
                  <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--accent-indigo-light)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Code size={14} /> Agent Internal Source Code & Prompt Logic
                  </h4>
                  <pre className="code-block">
                    {selectedAgentMeta.logic}
                  </pre>
                </div>
              )}

              {/* 3. Inputs & Outputs Payload */}
              {inspectorSubTab === 'payload' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  <div>
                    <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--accent-cyan)', marginBottom: '10px' }}>
                      Input State Parameters
                    </h4>
                    <pre className="code-block" style={{ maxHeight: '350px' }}>
                      {JSON.stringify(currentAgentExecution ? currentAgentExecution.inputs : { note: "Select an active case to view live state inputs" }, null, 2)}
                    </pre>
                  </div>

                  <div>
                    <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--accent-emerald)', marginBottom: '10px' }}>
                      Output State Results
                    </h4>
                    <pre className="code-block" style={{ maxHeight: '350px' }}>
                      {JSON.stringify(currentAgentExecution ? currentAgentExecution.outputs : { note: "Select an active case to view live state outputs" }, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {/* 4. Tool Dispatch */}
              {inspectorSubTab === 'tools' && (
                <div>
                  <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--accent-purple)', marginBottom: '10px' }}>
                    Dispatched Tool Calls & Queries ({currentAgentExecution && currentAgentExecution.tool_calls ? currentAgentExecution.tool_calls.length : 0})
                  </h4>

                  {currentAgentExecution && currentAgentExecution.tool_calls && currentAgentExecution.tool_calls.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {currentAgentExecution.tool_calls.map((tc, idx) => (
                        <div key={idx} style={{ background: 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '8px', borderLeft: '3px solid var(--accent-purple)', fontSize: '11px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span style={{ fontWeight: '700', color: 'var(--accent-purple)' }}>Tool: {tc.tool}</span>
                            <span className="badge badge-low">{tc.status}</span>
                          </div>
                          {tc.query && <div style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>Query: {tc.query}</div>}
                          {tc.algorithm && <div style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>Algorithm: {tc.algorithm}</div>}
                          {tc.ruleset && <div style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>Ruleset: {tc.ruleset}</div>}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>No tool calls executed for this node or no active case selected.</p>
                  )}
                </div>
              )}

              {/* 5. Audit Log Stream */}
              {inspectorSubTab === 'audit' && (
                <div>
                  <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--accent-amber)', marginBottom: '10px' }}>
                    Agent Filtered Audit Trail Stream ({currentAgentExecution && currentAgentExecution.audit_events ? currentAgentExecution.audit_events.length : 0} Records)
                  </h4>

                  {currentAgentExecution && currentAgentExecution.audit_events && currentAgentExecution.audit_events.length > 0 ? (
                    <div style={{ background: 'rgba(0,0,0,0.4)', padding: '12px', borderRadius: '8px', fontFamily: 'monospace', fontSize: '11px', maxHeight: '300px', overflowY: 'auto' }}>
                      {currentAgentExecution.audit_events.map((ae, idx) => (
                        <div key={idx} style={{ marginBottom: '6px', color: 'var(--text-secondary)' }}>
                          <span style={{ color: 'var(--text-muted)' }}>[{new Date(ae.timestamp).toISOString()}]</span> <strong style={{ color: 'var(--accent-indigo-light)' }}>{ae.actor}</strong> &rarr; <span style={{ color: '#fff' }}>{ae.action}</span>: {ae.summary}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>No audit events logged for this agent in current case.</p>
                  )}
                </div>
              )}

            </div>

          </div>
        )}

        {/* Tab: Investigation Planner */}
        {activeTab === 'planner' && (
          <InvestigationPlannerView apiBase={API_BASE} authToken={authToken} />
        )}

      </main>
    </div>
  );
}
