import React, { useState } from 'react';
import { ActionItem, AdvisoryResponse, UserProfile } from '../types/api';
import { api } from '../services/apiClient';

interface ActionDetailModalProps {
  action: ActionItem;
  user: UserProfile;
  onClose: () => void;
  onActionUpdated: () => void;
}

export const ActionDetailModal: React.FC<ActionDetailModalProps> = ({ action, user, onClose, onActionUpdated }) => {
  const [advisory, setAdvisory] = useState<AdvisoryResponse | null>(null);
  const [loadingAdvisory, setLoadingAdvisory] = useState(false);
  const [advisoryError, setAdvisoryError] = useState<string | null>(null);

  const [decision, setDecision] = useState<'APPROVE' | 'REJECT' | 'MODIFY_AND_APPROVE'>('APPROVE');
  const [rationale, setRationale] = useState('');
  const [modifiedPayloadStr, setModifiedPayloadStr] = useState(
    JSON.stringify(action.modified_payload || action.payload, null, 2)
  );
  const [submitting, setSubmitting] = useState(false);

  const isAdmin = user.roles.includes('admin');
  const isAnalyst = user.roles.includes('analyst') || isAdmin;
  const isCritical = action.risk_level === 'critical';
  const canReview = isCritical ? isAdmin : isAnalyst;

  const handleFetchAdvisory = async () => {
    try {
      setLoadingAdvisory(true); setAdvisoryError(null);
      const adv = await api.getAdvisory(action.id); setAdvisory(adv);
    } catch (err: any) { setAdvisoryError(err.message || 'Advisory failed'); }
    finally { setLoadingAdvisory(false); }
  };

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (rationale.trim().length < 5) return alert('Rationale min 5 characters required');
    let modPayload: any = undefined;
    if (decision === 'MODIFY_AND_APPROVE') {
      try { modPayload = JSON.parse(modifiedPayloadStr); } catch { return alert('Invalid JSON in modified payload'); }
    }
    try {
      setSubmitting(true);
      await api.reviewAction(action.id, { decision, rationale: rationale.trim(), modified_payload: modPayload });
      onActionUpdated(); onClose();
    } catch (err: any) { alert(err.message || 'Review failed'); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #374151', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h2>{action.id}</h2>
              <span className={`badge badge-${action.risk_level}`}>{action.risk_score} • {action.risk_level}</span>
              <span className={`badge badge-${action.status}`}>{action.status.replace(/_/g, ' ')}</span>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Agent: {action.agent_id} ({action.agent_framework}) • Session: {action.session_id}</div>
          </div>
          <button className="btn btn-outline" onClick={onClose}>✕</button>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <div style={{ fontSize: '0.75rem', color: '#9ca3af', textTransform: 'uppercase', fontWeight: 600 }}>Intent & Resource</div>
          <p style={{ background: '#1e293b', padding: '0.5rem', borderRadius: '6px', marginTop: '0.25rem' }}>{action.intent}</p>
          <div style={{ marginTop: '0.25rem', fontSize: '0.8rem' }}>Target: <code>{action.target_resource}</code></div>
          {action.expires_at && <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', color: '#9ca3af' }}>Proposal deadline: {action.expires_at}</div>}
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <div style={{ fontSize: '0.75rem', color: '#9ca3af', textTransform: 'uppercase', fontWeight: 600 }}>Proposed Payload</div>
          <pre>{JSON.stringify(action.payload, null, 2)}</pre>
          {action.modified_payload && (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ fontSize: '0.75rem', color: '#c084fc', textTransform: 'uppercase', fontWeight: 600 }}>Modified Payload</div>
              <pre style={{ border: '1px solid #7e22ce' }}>{JSON.stringify(action.modified_payload, null, 2)}</pre>
            </div>
          )}
        </div>

        {action.violations && action.violations.length > 0 && (
          <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#450a0a', border: '1px solid #991b1b', borderRadius: '6px' }}>
            <div style={{ fontWeight: 600, color: '#fca5a5' }}>⚠️ Triggered Policies ({action.violations.length})</div>
            {action.violations.map((v, i) => (
              <div key={i} style={{ fontSize: '0.8rem', color: '#fee2e2' }}>• {v.policy_name} ({v.severity.toUpperCase()}): {v.matched_detail}</div>
            ))}
          </div>
        )}

        <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div><div style={{ fontWeight: 600 }}>Grounded LLM Security Advisory</div><div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Opt-in advisory (deterministic offline fallback)</div></div>
            <button type="button" className="btn btn-outline" style={{ fontSize: '0.75rem' }} onClick={handleFetchAdvisory} disabled={loadingAdvisory}>
              {loadingAdvisory ? 'Analyzing...' : advisory ? 'Refresh' : 'Generate Advisory'}
            </button>
          </div>
          {advisoryError && <div style={{ color: '#f87171', fontSize: '0.8rem', marginTop: '0.5rem' }}>{advisoryError}</div>}
          {advisory && (
            <div style={{ marginTop: '0.5rem', borderTop: '1px solid #1e293b', paddingTop: '0.5rem', fontSize: '0.8rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.35rem' }}>
                <span className="badge badge-low">{advisory.provider}</span>
                <span className="badge badge-pending">{advisory.model}</span>
                {advisory.offline_deterministic && <span className="badge badge-medium">Offline Deterministic</span>}
              </div>
              <p><strong>Summary:</strong> {advisory.summary}</p>
              <p style={{ marginTop: '0.25rem' }}><strong>Blast Radius:</strong> {advisory.blast_radius_assessment}</p>
              {advisory.security_concerns.length > 0 && <p style={{ color: '#fca5a5', marginTop: '0.25rem' }}><strong>Concerns:</strong> {advisory.security_concerns.join(', ')}</p>}
            </div>
          )}
        </div>

        {action.status === 'expired' ? (
          <div style={{ padding: '0.75rem', background: '#1e293b', borderRadius: '8px', color: '#fde68a' }}>This proposal passed its deadline and can no longer be claimed or approved.</div>
        ) : ['pending', 'under_review'].includes(action.status) ? (
          <div style={{ padding: '0.75rem', background: '#1e293b', borderRadius: '8px' }}>
            <h4 style={{ marginBottom: '0.5rem' }}>Human Review Decision</h4>
            {isCritical && !isAdmin && <div style={{ padding: '0.5rem', background: '#7f1d1d', borderRadius: '4px', color: '#fecaca', marginBottom: '0.5rem', fontSize: '0.8rem' }}>⛔ CRITICAL action requires Admin role to review.</div>}
            {!isAnalyst && <div style={{ padding: '0.5rem', background: '#374151', borderRadius: '4px', color: '#e5e7eb', marginBottom: '0.5rem', fontSize: '0.8rem' }}>🔒 Viewer role is read-only.</div>}
            <form onSubmit={handleReviewSubmit}>
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
                <label><input type="radio" name="d" value="APPROVE" checked={decision === 'APPROVE'} onChange={() => setDecision('APPROVE')} disabled={!canReview} /> Approve</label>
                <label><input type="radio" name="d" value="MODIFY_AND_APPROVE" checked={decision === 'MODIFY_AND_APPROVE'} onChange={() => setDecision('MODIFY_AND_APPROVE')} disabled={!canReview} /> Modify & Approve</label>
                <label><input type="radio" name="d" value="REJECT" checked={decision === 'REJECT'} onChange={() => setDecision('REJECT')} disabled={!canReview} /> Reject</label>
              </div>
              {decision === 'MODIFY_AND_APPROVE' && (
                <div style={{ marginBottom: '0.5rem' }}><label style={{ fontSize: '0.75rem', color: '#c084fc' }}>Modified payload. Edits are re-scored before approval.</label><textarea className="search-input" style={{ width: '100%', height: '80px', fontFamily: 'monospace' }} value={modifiedPayloadStr} onChange={e => setModifiedPayloadStr(e.target.value)} disabled={!canReview} required /></div>
              )}
              <div style={{ marginBottom: '0.5rem' }}><label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Rationale</label><textarea className="search-input" style={{ width: '100%', height: '60px' }} placeholder="Mandatory rationale (min 5 chars)..." value={rationale} onChange={e => setRationale(e.target.value)} disabled={!canReview} required /></div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
                <button type="submit" className={decision === 'REJECT' ? 'btn btn-danger' : 'btn btn-success'} disabled={!canReview || submitting}>{submitting ? 'Signing...' : decision}</button>
              </div>
            </form>
          </div>
        ) : (
          <div style={{ padding: '0.75rem', background: '#1e293b', borderRadius: '8px' }}>
            <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Reviewed by: <strong>{action.reviewer_id}</strong> ({action.reviewer_role}) at {action.reviewed_at}</div>
            <p style={{ marginTop: '0.25rem' }}><strong>Rationale:</strong> {action.rationale}</p>
          </div>
        )}
      </div>
    </div>
  );
};
