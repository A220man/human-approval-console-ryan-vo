import React, { useState, useEffect } from 'react';
import { ReceiptItem, ReceiptVerifyResult } from '../types/api';
import { api } from '../services/apiClient';

export const ReceiptsView: React.FC = () => {
  const [receipts, setReceipts] = useState<ReceiptItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifyResult, setVerifyResult] = useState<ReceiptVerifyResult | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [exportContent, setExportContent] = useState<string | null>(null);
  const [exportReceiptId, setExportReceiptId] = useState<string | null>(null);

  const loadReceipts = async () => {
    try {
      setLoading(true); setError(null);
      const res = await api.getReceipts(); setReceipts(res.items);
    } catch (err: any) { setError(err.message || 'Failed to fetch receipts'); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadReceipts(); }, []);

  const handleVerify = async (id: string) => {
    try {
      setVerifyingId(id);
      const res = await api.verifyReceipt(id); setVerifyResult(res);
    } catch (err: any) { alert(err.message); }
    finally { setVerifyingId(null); }
  };

  const handleExport = async (id: string) => {
    try {
      const text = await api.exportReceiptMarkdown(id);
      setExportContent(text); setExportReceiptId(id);
    } catch (err: any) { alert(err.message); }
  };

  const handleDownload = () => {
    if (!exportContent || !exportReceiptId) return;
    const blob = new Blob([exportContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `${exportReceiptId}.md`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2>Cryptographically Signed Approval Receipts</h2>
          <p style={{ fontSize: '0.85rem', color: '#9ca3af' }}>Immutable audit ledger secured with HMAC-SHA256 signatures and hash chaining.</p>
        </div>
        <button className="btn btn-outline" onClick={loadReceipts}>Refresh Ledger</button>
      </div>

      {loading ? <div style={{ textAlign: 'center', padding: '3rem', color: '#9ca3af' }}>Loading receipts...</div>
      : error ? <div style={{ padding: '1rem', background: '#7f1d1d', borderRadius: '8px', color: '#fecaca' }}>{error}</div>
      : receipts.length === 0 ? <div style={{ textAlign: 'center', padding: '3rem', background: '#111827', borderRadius: '8px' }}>No receipts generated yet.</div>
      : (
        <div className="table-container">
          <table>
            <thead><tr><th>Receipt ID / Action</th><th>Decision</th><th>Reviewer</th><th>Signed (UTC)</th><th>Payload SHA-256</th><th>Actions</th></tr></thead>
            <tbody>
              {receipts.map(r => (
                <tr key={r.id}>
                  <td><div style={{ fontWeight: 600 }}>{r.id}</div><div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Action: {r.action_id}</div></td>
                  <td><span className={`badge badge-${r.decision.toLowerCase()}`}>{r.decision}</span></td>
                  <td><div style={{ fontSize: '0.85rem' }}>{r.reviewer_id}</div><div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Role: {r.reviewer_role}</div></td>
                  <td style={{ fontSize: '0.8rem', color: '#9ca3af' }}>{r.signed_at.slice(0, 19).replace('T', ' ')}</td>
                  <td><code style={{ fontSize: '0.75rem' }}>{r.payload_hash.slice(0, 16)}...</code></td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      <button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }} onClick={() => handleVerify(r.id)} disabled={verifyingId === r.id}>{verifyingId === r.id ? 'Verifying...' : 'Verify'}</button>
                      <button className="btn btn-outline" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }} onClick={() => handleExport(r.id)}>Export</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {verifyResult && (
        <div className="modal-backdrop" onClick={() => setVerifyResult(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h3>Receipt Verification Audit</h3><button className="btn btn-outline" onClick={() => setVerifyResult(null)}>✕</button>
            </div>
            <div style={{ padding: '0.75rem', background: verifyResult.is_valid ? '#064e3b' : '#7f1d1d', borderRadius: '8px', marginBottom: '1rem' }}>
              <div style={{ fontWeight: 700, color: verifyResult.is_valid ? '#a7f3d0' : '#fecaca' }}>{verifyResult.is_valid ? '✓ Cryptographic Signature & Hash Chain Verified' : '✗ Verification Failed'}</div>
              <div style={{ fontSize: '0.8rem', color: '#fff' }}>{verifyResult.details}</div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '1rem', fontSize: '0.8rem' }}>
              <div style={{ background: '#1e293b', padding: '0.5rem', borderRadius: '4px' }}>Signature: <strong>{verifyResult.signature_valid ? 'Valid' : 'Invalid'}</strong></div>
              <div style={{ background: '#1e293b', padding: '0.5rem', borderRadius: '4px' }}>Payload Hash: <strong>{verifyResult.payload_hash_matches ? 'Matches' : 'Mismatch'}</strong></div>
              <div style={{ background: '#1e293b', padding: '0.5rem', borderRadius: '4px' }}>Rationale Hash: <strong>{verifyResult.rationale_hash_matches ? 'Matches' : 'Mismatch'}</strong></div>
              <div style={{ background: '#1e293b', padding: '0.5rem', borderRadius: '4px' }}>Chain Link: <strong>{verifyResult.chain_link_intact ? 'Intact' : 'Broken'}</strong></div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}><button className="btn btn-primary" onClick={() => setVerifyResult(null)}>Close</button></div>
          </div>
        </div>
      )}

      {exportContent && (
        <div className="modal-backdrop" onClick={() => setExportContent(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h3>Export Approval Receipt</h3><button className="btn btn-outline" onClick={() => setExportContent(null)}>✕</button>
            </div>
            <pre style={{ maxHeight: '300px', marginBottom: '1rem' }}>{exportContent}</pre>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button className="btn btn-outline" onClick={() => setExportContent(null)}>Close</button>
              <button className="btn btn-primary" onClick={handleDownload}>Download .md</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
