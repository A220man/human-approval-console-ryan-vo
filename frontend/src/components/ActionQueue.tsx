import React, { useState, useEffect } from 'react';
import { ActionItem, QueueStats, UserProfile } from '../types/api';
import { api } from '../services/apiClient';

interface ActionQueueProps {
  user: UserProfile;
  onSelectAction: (action: ActionItem) => void;
}

export const ActionQueue: React.FC<ActionQueueProps> = ({ user, onSelectAction }) => {
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [stats, setStats] = useState<QueueStats>({ pending: 0, under_review: 0, approved: 0, rejected: 0, critical_pending: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const [showSimModal, setShowSimModal] = useState(false);
  const [simAgent, setSimAgent] = useState('autonomous-devops-agent');
  const [simType, setSimType] = useState('shell_command');
  const [simTarget, setSimTarget] = useState('prod-k8s-worker-02');
  const [simIntent, setSimIntent] = useState('Purge cache logs to alleviate disk pressure');
  const [simPayload, setSimPayload] = useState('{\n  "command": "rm -rf /var/cache/app/* && systemctl reload app"\n}');
  const [submitting, setSubmitting] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true); setError(null);
      const res = await api.getActions({ status: statusFilter || undefined, risk_level: riskFilter || undefined, action_type: typeFilter || undefined, search: searchTerm || undefined });
      setActions(res.items); setStats(res.stats);
    } catch (err: any) { setError(err.message || 'Failed to fetch queue'); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadData(); }, [statusFilter, riskFilter, typeFilter, searchTerm]);

  const handleClaim = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try { await api.claimAction(id); loadData(); } catch (err: any) { alert(err.message); }
  };

  const handleSimulateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      const payload = JSON.parse(simPayload);
      await api.ingestAction({
        agent_id: simAgent, agent_framework: 'langchain',
        session_id: `sess-${Math.random().toString(36).slice(2, 8)}`,
        action_type: simType, target_resource: simTarget, intent: simIntent, payload, expires_in_minutes: 120
      });
      setShowSimModal(false); loadData();
    } catch (err: any) { alert(err.message || 'Invalid JSON'); }
    finally { setSubmitting(false); }
  };

  const canClaim = user.roles.includes('analyst') || user.roles.includes('admin');

  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card"><div className="label">Pending Review</div><div className="value" style={{ color: '#38bdf8' }}>{stats.pending}</div></div>
        <div className="stat-card"><div className="label">Under Active Review</div><div className="value" style={{ color: '#fbbf24' }}>{stats.under_review}</div></div>
        <div className="stat-card"><div className="label">Critical Risk Pending</div><div className="value" style={{ color: stats.critical_pending > 0 ? '#f87171' : '#9ca3af' }}>{stats.critical_pending}</div></div>
        <div className="stat-card"><div className="label">Approved Decisions</div><div className="value" style={{ color: '#34d399' }}>{stats.approved}</div></div>
        <div className="stat-card"><div className="label">Rejected Actions</div><div className="value" style={{ color: '#f87171' }}>{stats.rejected}</div></div>
      </div>

      <div className="filter-bar">
        <input type="text" className="search-input" placeholder="Search intent, resource, agent ID..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
        <select className="select-input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="under_review">Under Review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="modified_and_approved">Modified & Approved</option>
        </select>
        <select className="select-input" value={riskFilter} onChange={e => setRiskFilter(e.target.value)}>
          <option value="">All Risk Tiers</option>
          <option value="critical">Critical (85-100)</option>
          <option value="high">High (65-84)</option>
          <option value="medium">Medium (35-64)</option>
          <option value="low">Low (0-34)</option>
        </select>
        <select className="select-input" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
          <option value="">All Action Types</option>
          <option value="shell_command">Shell Command</option>
          <option value="database_query">Database Query</option>
          <option value="privilege_escalation">Privilege Escalation</option>
          <option value="file_mutation">File Mutation</option>
          <option value="financial_transaction">Financial Transaction</option>
          <option value="api_call">API Call</option>
        </select>
        <button className="btn btn-primary" onClick={() => setShowSimModal(true)}>+ Ingest Agent Proposal</button>
      </div>

      {loading ? <div style={{ textAlign: 'center', padding: '3rem', color: '#9ca3af' }}>Loading proposed agent actions...</div>
      : error ? <div style={{ padding: '1.5rem', background: '#7f1d1d', borderRadius: '8px', color: '#fecaca' }}>Error: {error}</div>
      : actions.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem', background: '#111827', borderRadius: '8px', border: '1px solid #374151' }}>
          <h3>No action proposals found</h3><p style={{ color: '#9ca3af' }}>Click "+ Ingest Agent Proposal" to simulate agent actions.</p>
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr><th>Action ID / Agent</th><th>Type</th><th>Target Resource</th><th>Proposed Intent</th><th>Risk Evaluation</th><th>Status</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {actions.map(act => (
                <tr key={act.id} style={{ cursor: 'pointer' }} onClick={() => onSelectAction(act)}>
                  <td><div style={{ fontWeight: 600 }}>{act.id}</div><div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>{act.agent_id}</div></td>
                  <td><span style={{ fontSize: '0.8rem', background: '#1f2937', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>{act.action_type}</span></td>
                  <td><code style={{ fontSize: '0.8rem' }}>{act.target_resource}</code></td>
                  <td><div style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{act.intent}</div></td>
                  <td><span className={`badge badge-${act.risk_level}`}>{act.risk_score} • {act.risk_level}</span></td>
                  <td><span className={`badge badge-${act.status}`}>{act.status.replace(/_/g, ' ')}</span></td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      {act.status === 'pending' && canClaim && (
                        <button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }} onClick={e => handleClaim(e, act.id)}>Claim</button>
                      )}
                      <button className="btn btn-primary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }} onClick={() => onSelectAction(act)}>Inspect</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showSimModal && (
        <div className="modal-backdrop" onClick={() => setShowSimModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h3>Simulate Autonomous Agent Proposal</h3><button className="btn btn-outline" onClick={() => setShowSimModal(false)}>✕</button>
            </div>
            <form onSubmit={handleSimulateSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                <div><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Agent ID</label><input type="text" className="search-input" style={{ width: '100%' }} value={simAgent} onChange={e => setSimAgent(e.target.value)} required /></div>
                <div><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Action Type</label>
                  <select className="select-input" style={{ width: '100%' }} value={simType} onChange={e => setSimType(e.target.value)}>
                    <option value="shell_command">shell_command</option><option value="database_query">database_query</option>
                    <option value="privilege_escalation">privilege_escalation</option><option value="file_mutation">file_mutation</option>
                    <option value="financial_transaction">financial_transaction</option><option value="api_call">api_call</option>
                  </select>
                </div>
              </div>
              <div style={{ marginBottom: '0.75rem' }}><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Target Resource</label><input type="text" className="search-input" style={{ width: '100%' }} value={simTarget} onChange={e => setSimTarget(e.target.value)} required /></div>
              <div style={{ marginBottom: '0.75rem' }}><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Stated Intent</label><input type="text" className="search-input" style={{ width: '100%' }} value={simIntent} onChange={e => setSimIntent(e.target.value)} required /></div>
              <div style={{ marginBottom: '1rem' }}><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Payload JSON</label><textarea className="search-input" style={{ width: '100%', height: '100px', fontFamily: 'monospace' }} value={simPayload} onChange={e => setSimPayload(e.target.value)} required /></div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowSimModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>{submitting ? 'Ingesting...' : 'Ingest Proposal'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
