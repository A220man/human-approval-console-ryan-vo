import React, { useState, useEffect } from 'react';
import { PolicyItem, UserProfile } from '../types/api';
import { api } from '../services/apiClient';

interface PolicyManagerProps {
  user: UserProfile;
}

export const PolicyManager: React.FC<PolicyManagerProps> = ({ user }) => {
  const [policies, setPolicies] = useState<PolicyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [actionType, setActionType] = useState('shell_command');
  const [rulePattern, setRulePattern] = useState('');
  const [severity, setSeverity] = useState<'low' | 'medium' | 'high' | 'critical'>('high');
  const [requiredRole, setRequiredRole] = useState<'analyst' | 'admin'>('analyst');
  const [submitting, setSubmitting] = useState(false);

  const isAdmin = user.roles.includes('admin');

  const loadPolicies = async () => {
    try {
      setLoading(true); setError(null);
      const list = await api.getPolicies(); setPolicies(list);
    } catch (err: any) { setError(err.message || 'Failed to fetch policies'); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadPolicies(); }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this policy?')) return;
    try { await api.deletePolicy(id); loadPolicies(); } catch (err: any) { alert(err.message); }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await api.createPolicy({ name, description, action_type: actionType, rule_pattern: rulePattern, severity, required_role: requiredRole, auto_reject: false, enabled: true });
      setShowAdd(false); setName(''); setDescription(''); setRulePattern(''); loadPolicies();
    } catch (err: any) { alert(err.message); }
    finally { setSubmitting(false); }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2>Security Guardrail Policies</h2>
          <p style={{ fontSize: '0.85rem', color: '#9ca3af' }}>Deterministic pattern matching rules and role escalation thresholds.</p>
        </div>
        {isAdmin && <button className="btn btn-primary" onClick={() => setShowAdd(true)}>+ Add Policy</button>}
      </div>

      {loading ? <div style={{ textAlign: 'center', padding: '3rem', color: '#9ca3af' }}>Loading policies...</div>
      : error ? <div style={{ padding: '1rem', background: '#7f1d1d', borderRadius: '8px', color: '#fecaca' }}>{error}</div>
      : policies.length === 0 ? <div style={{ textAlign: 'center', padding: '3rem', background: '#111827', borderRadius: '8px' }}>No policies configured.</div>
      : (
        <div className="table-container">
          <table>
            <thead><tr><th>Name & Description</th><th>Scope</th><th>Rule Pattern</th><th>Severity</th><th>Required Role</th>{isAdmin && <th>Action</th>}</tr></thead>
            <tbody>
              {policies.map(p => (
                <tr key={p.id}>
                  <td><div style={{ fontWeight: 600 }}>{p.name}</div><div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>{p.description}</div></td>
                  <td><span style={{ fontSize: '0.8rem', background: '#1f2937', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>{p.action_type}</span></td>
                  <td><code style={{ fontSize: '0.75rem' }}>{p.rule_pattern}</code></td>
                  <td><span className={`badge badge-${p.severity}`}>{p.severity}</span></td>
                  <td><strong>{p.required_role.toUpperCase()}</strong></td>
                  {isAdmin && <td><button className="btn btn-danger" style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }} onClick={() => handleDelete(p.id)}>Delete</button></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && (
        <div className="modal-backdrop" onClick={() => setShowAdd(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h3>Add Safety Policy</h3><button className="btn btn-outline" onClick={() => setShowAdd(false)}>✕</button>
            </div>
            <form onSubmit={handleCreate}>
              <div style={{ marginBottom: '0.75rem' }}><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Name</label><input type="text" className="search-input" style={{ width: '100%' }} value={name} onChange={e => setName(e.target.value)} required /></div>
              <div style={{ marginBottom: '0.75rem' }}><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Description</label><input type="text" className="search-input" style={{ width: '100%' }} value={description} onChange={e => setDescription(e.target.value)} required /></div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Action Type</label>
                  <select className="select-input" style={{ width: '100%' }} value={actionType} onChange={e => setActionType(e.target.value)}>
                    <option value="all">all</option><option value="shell_command">shell_command</option><option value="database_query">database_query</option>
                    <option value="privilege_escalation">privilege_escalation</option><option value="file_mutation">file_mutation</option><option value="financial_transaction">financial_transaction</option><option value="api_call">api_call</option>
                  </select>
                </div>
                <div><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Severity</label>
                  <select className="select-input" style={{ width: '100%' }} value={severity} onChange={e => setSeverity(e.target.value as any)}>
                    <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
                  </select>
                </div>
              </div>
              <div style={{ marginBottom: '0.75rem' }}><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Rule Regex Pattern</label><input type="text" className="search-input" style={{ width: '100%', fontFamily: 'monospace' }} value={rulePattern} onChange={e => setRulePattern(e.target.value)} required /></div>
              <div style={{ marginBottom: '1rem' }}><label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Required Role</label>
                <select className="select-input" style={{ width: '100%' }} value={requiredRole} onChange={e => setRequiredRole(e.target.value as any)}>
                  <option value="analyst">Analyst</option><option value="admin">Admin</option>
                </select>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button type="button" className="btn btn-outline" onClick={() => setShowAdd(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>{submitting ? 'Saving...' : 'Save Policy'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
