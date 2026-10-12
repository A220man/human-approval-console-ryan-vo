import React, { useState, useEffect } from 'react';
import { ActionItem, AdvisoryResponse, AuditLogEntry, ReceiptVerifyResult, UserProfile } from '../types/api';
import { api } from '../services/apiClient';

interface ActionDetailModalProps {
  action: ActionItem;
  user: UserProfile;
  onClose: () => void;
  onActionUpdated: () => void;
}

export const ActionDetailModal: React.FC<ActionDetailModalProps> = ({ action, user, onClose, onActionUpdated }) => {
  const [auditTrail, setAuditTrail] = useState<AuditLogEntry[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [advisory, setAdvisory] = useState<AdvisoryResponse | null>(null);
  const [loadingAdvisory, setLoadingAdvisory] = useState(false);
  const [advisoryError, setAdvisoryError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoadingAudit(true);
    api.getActionAuditTrail(action.id)
      .then(logs => { if (active) setAuditTrail(logs); })
      .catch(() => {})
      .finally(() => { if (active) setLoadingAudit(false); });
    return () => { active = false; };
  }, [action.id]);

  const [decision, setDecision] = useState<'APPROVE' | 'REJECT' | 'MODIFY_AND_APPROVE'>('APPROVE');
  const [rationale, setRationale] = useState('');
  const [modifiedPayloadStr, setModifiedPayloadStr] = useState(
    JSON.stringify(action.modified_payload || action.payload, null, 2)
  );
  const [submitting, setSubmitting] = useState(false);
  const [receiptAudit, setReceiptAudit] = useState<ReceiptVerifyResult | null>(null);
  const [verifyingReceipt, setVerifyingReceipt] = useState(false);

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

  const handleVerifyReceiptInline = async () => {
    if (!action.receipt_id) return;
    try {
      setVerifyingReceipt(true);
      const res = await api.verifyReceipt(action.receipt_id);
      setReceiptAudit(res);
    } catch (err: any) { alert(err.message || 'Receipt verification failed'); }
    finally { setVerifyingReceipt(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="flex-between mb-4" style={{ borderBottom: '1px solid #374151', paddingBottom: '0.75rem' }}>
          <div>
            <div className="flex-row">
              <h2>{action.id}</h2>
              <span className={`badge badge-${action.risk_level}`}>{action.risk_score} • {action.risk_level}</span>
              <span className={`badge badge-${action.status}`}>{action.status.replace(/_/g, ' ')}</span>
            </div>
            <div className="meta-text">Agent: {action.agent_id} ({action.agent_framework}) • Session: {action.session_id}</div>
          </div>
          <button className="btn btn-outline" onClick={onClose}>✕</button>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <div className="section-title">Intent & Resource</div>
          <p className="sub-card">{action.intent}</p>
          <div style={{ marginTop: '0.25rem', fontSize: '0.8rem' }}>Target: <code>{action.target_resource}</code></div>
          {action.expires_at && <div className="meta-text" style={{ marginTop: '0.25rem', fontSize: '0.75rem' }}>Proposal deadline: {action.expires_at}</div>}
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <div className="section-title">Proposed Payload</div>
          <pre>{JSON.stringify(action.payload, null, 2)}</pre>
          {action.modified_payload && (
            <div style={{ marginTop: '0.5rem' }}>
              <div className="section-title" style={{ color: '#c084fc' }}>Modified Payload</div>
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

        <div className="card-section">
          <div className="flex-between">
            <div><div style={{ fontWeight: 600 }}>Grounded LLM Security Advisory</div><div className="meta-text" style={{ fontSize: '0.75rem' }}>Opt-in advisory (deterministic offline fallback)</div></div>
            <button type="button" className="btn btn-outline" style={{ fontSize: '0.75rem' }} onClick={handleFetchAdvisory} disabled={loadingAdvisory}>
              {loadingAdvisory ? 'Analyzing...' : advisory ? 'Refresh' : 'Generate Advisory'}
            </button>
          </div>
          {advisoryError && <div style={{ color: '#f87171', fontSize: '0.8rem', marginTop: '0.5rem' }}>{advisoryError}</div>}
          {advisory && (
            <div style={{ marginTop: '0.5rem', borderTop: '1px solid #1e293b', paddingTop: '0.5rem', fontSize: '0.8rem' }}>
              <div className="flex-row" style={{ marginBottom: '0.35rem' }}>
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

        <div className="card-section">
          <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.85rem' }}>Audit Trail & Custody History ({auditTrail.length})</div>
          {loadingAudit ? (
            <div className="meta-text" style={{ fontSize: '0.75rem' }}>Loading audit events...</div>
          ) : auditTrail.length === 0 ? (
            <div className="meta-text" style={{ fontSize: '0.75rem' }}>No audit log events recorded yet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {auditTrail.map(entry => (
                <div key={entry.id} className="timeline-item">
                  <div className="flex-row">
                    <span className="badge badge-pending" style={{ fontSize: '0.7rem' }}>{entry.event_type}</span>
                    <span><strong>{entry.actor_id}</strong> ({entry.actor_role})</span>
                  </div>
                  <span style={{ color: '#9ca3af', fontFamily: 'monospace' }}>{entry.created_at.slice(0, 19).replace('T', ' ')}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {action.status === 'expired' ? (
          <div className="sub-card" style={{ color: '#fde68a' }}>This proposal passed its deadline and can no longer be claimed or approved.</div>
        ) : ['pending', 'under_review'].includes(action.status) ? (
          <div className="sub-card">
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
              <div style={{ marginBottom: '0.5rem' }}><label className="meta-text" style={{ fontSize: '0.75rem' }}>Rationale</label><textarea className="search-input" style={{ width: '100%', height: '60px' }} placeholder="Mandatory rationale (min 5 chars)..." value={rationale} onChange={e => setRationale(e.target.value)} disabled={!canReview} required /></div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
                <button type="submit" className={decision === 'REJECT' ? 'btn btn-danger' : 'btn btn-success'} disabled={!canReview || submitting}>{submitting ? 'Signing...' : decision}</button>
              </div>
            </form>
          </div>
        ) : (
          <div className="sub-card">
            <div className="meta-text">Reviewed by: <strong>{action.reviewer_id}</strong> ({action.reviewer_role}) at {action.reviewed_at}</div>
            <p style={{ marginTop: '0.25rem' }}><strong>Rationale:</strong> {action.rationale}</p>
            {action.receipt_id && (
              <div className="flex-between" style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid #374151' }}>
                <div><span className="meta-text" style={{ fontSize: '0.75rem' }}>Receipt: </span><code style={{ fontSize: '0.8rem', color: '#38bdf8' }}>{action.receipt_id}</code></div>
                <button type="button" className="btn btn-secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }} onClick={handleVerifyReceiptInline} disabled={verifyingReceipt}>{verifyingReceipt ? 'Verifying...' : 'Verify Receipt'}</button>
              </div>
            )}
            {receiptAudit && (
              <div style={{ marginTop: '0.5rem', padding: '0.4rem 0.6rem', background: receiptAudit.is_valid ? '#064e3b' : '#7f1d1d', borderRadius: '4px', fontSize: '0.75rem', color: '#fff' }}>
                {receiptAudit.is_valid ? '✓ HMAC Signature & Hash Chain Verified' : '✗ Verification Failed'} ({receiptAudit.details})
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
