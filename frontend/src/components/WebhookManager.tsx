import React, { useState, useEffect } from 'react';
import { UserProfile, Webhook } from '../types/api';
import { api } from '../services/apiClient';

const EVENT_TYPES = ['action.approved', 'action.rejected', 'webhook.test'] as const;

interface WebhookFormData {
  name: string;
  url: string;
  secret: string;
  event_filter: string;
  enabled: boolean;
  max_retries: number;
}

export const WebhookManager: React.FC<{ user: UserProfile }> = ({ user }) => {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<Webhook | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [formData, setFormData] = useState<WebhookFormData>({
    name: '',
    url: '',
    secret: '',
    event_filter: 'action.approved',
    enabled: true,
    max_retries: 5,
  });

  const loadWebhooks = async () => {
    try {
      setLoading(true);
      const resp = await api.getWebhooks();
      setWebhooks(resp.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load webhooks';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWebhooks();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const eventFilter = formData.event_filter
        ? formData.event_filter.split(',').map(s => s.trim()).filter(Boolean)
        : [];

      if (editingWebhook) {
        await api.updateWebhook(editingWebhook.id, {
          name: formData.name,
          url: formData.url,
          secret: formData.secret || undefined,
          event_filter: eventFilter.length > 0 ? eventFilter : undefined,
          enabled: formData.enabled,
          max_retries: formData.max_retries,
        });
      } else {
        await api.createWebhook({
          name: formData.name,
          url: formData.url,
          secret: formData.secret || undefined,
          event_filter: eventFilter.length > 0 ? eventFilter : undefined,
          enabled: formData.enabled,
          max_retries: formData.max_retries,
        });
      }
      setShowCreateModal(false);
      setEditingWebhook(null);
      resetForm();
      loadWebhooks();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save webhook';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (webhook: Webhook) => {
    setEditingWebhook(webhook);
    setFormData({
      name: webhook.name,
      url: webhook.url,
      secret: webhook.secret || '',
      event_filter: webhook.event_filter?.join(', ') || '',
      enabled: webhook.enabled,
      max_retries: webhook.max_retries,
    });
    setShowCreateModal(true);
  };

  const handleDelete = async (webhook: Webhook) => {
    if (!window.confirm(`Delete webhook "${webhook.name}"?`)) return;
    try {
      await api.deleteWebhook(webhook.id);
      loadWebhooks();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete webhook';
      setError(msg);
    }
  };

  const handleTest = async (webhook: Webhook) => {
    try {
      setError(null);
      const resp = await api.testWebhook(webhook.id);
      if (resp.success) {
        alert(`Test webhook delivered successfully (attempt ${resp.attempt}, status ${resp.status_code})`);
      } else {
        alert(`Test webhook failed: ${resp.error || 'Unknown error'}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to test webhook';
      setError(msg);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      url: '',
      secret: '',
      event_filter: 'action.approved',
      enabled: true,
      max_retries: 5,
    });
  };

  const handleNew = () => {
    setEditingWebhook(null);
    resetForm();
    setShowCreateModal(true);
  };

  if (loading) {
    return <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>Loading webhooks…</div>;
  }

  const canManage = user.roles.includes('admin');

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 style={{ margin: 0 }}>Webhook Dispatch</h2>
        {canManage && (
          <button className="btn btn-primary" onClick={handleNew}>
            + Add Webhook
          </button>
        )}
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

      <div className="card">
        {webhooks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: '#9ca3af' }}>
            {canManage ? (
              <>
                <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>No webhooks configured</p>
                <p style={{ fontSize: '0.875rem' }}>Add a webhook to receive notifications when actions are approved</p>
              </>
            ) : (
              <p>No webhooks configured. Contact an administrator to set up webhook dispatch.</p>
            )}
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>URL</th>
                  <th>Events</th>
                  <th>Retries</th>
                  <th>Status</th>
                  <th style={{ width: '120px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {webhooks.map((wh) => (
                  <tr key={wh.id}>
                    <td style={{ fontWeight: 500 }}>{wh.name}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8125rem', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {wh.url}
                    </td>
                    <td>
                      {wh.event_filter && wh.event_filter.length > 0 ? (
                        wh.event_filter.map(e => <span key={e} className="badge badge-info" style={{ marginRight: '0.25rem' }}>{e}</span>)
                      ) : (
                        <span className="badge badge-muted">All events</span>
                      )}
                    </td>
                    <td>{wh.max_retries}</td>
                    <td>
                      <span className={`badge ${wh.enabled ? 'badge-success' : 'badge-muted'}`}>
                        {wh.enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </td>
                    <td>
                      {canManage && (
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button className="btn btn-sm btn-outline" onClick={() => handleEdit(wh)} title="Edit">
                            ✎
                          </button>
                          <button className="btn btn-sm btn-outline" onClick={() => handleTest(wh)} title="Test">
                            ▶
                          </button>
                          <button className="btn btn-sm btn-danger" onClick={() => handleDelete(wh)} title="Delete">
                            🗑
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => { setShowCreateModal(false); setEditingWebhook(null); resetForm(); }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingWebhook ? 'Edit Webhook' : 'Create Webhook'}</h3>
              <button className="modal-close" onClick={() => { setShowCreateModal(false); setEditingWebhook(null); resetForm(); }}>×</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <label className="form-label">Name</label>
                  <input
                    className="form-input"
                    type="text"
                    value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    required
                    placeholder="e.g., Production Deployments"
                  />
                </div>
                <div>
                  <label className="form-label">URL <span className="required">*</span></label>
                  <input
                    className="form-input"
                    type="url"
                    value={formData.url}
                    onChange={e => setFormData({ ...formData, url: e.target.value })}
                    required
                    placeholder="https://example.com/webhook"
                  />
                </div>
                <div>
                  <label className="form-label">Secret (optional)</label>
                  <input
                    className="form-input"
                    type="password"
                    value={formData.secret}
                    onChange={e => setFormData({ ...formData, secret: e.target.value })}
                    placeholder="HMAC secret for signature verification"
                  />
                  <p className="form-hint">Used to sign payloads with X-Webhook-Signature header (HMAC-SHA256)</p>
                </div>
                <div>
                  <label className="form-label">Event Filter (comma-separated)</label>
                  <input
                    className="form-input"
                    type="text"
                    value={formData.event_filter}
                    onChange={e => setFormData({ ...formData, event_filter: e.target.value })}
                    placeholder="action.approved, action.rejected"
                  />
                  <p className="form-hint">Leave empty for all events. Available: {EVENT_TYPES.join(', ')}</p>
                </div>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <div style={{ flex: 1 }}>
                    <label className="form-label">Max Retries</label>
                    <input
                      className="form-input"
                      type="number"
                      min="1"
                      max="20"
                      value={formData.max_retries}
                      onChange={e => setFormData({ ...formData, max_retries: parseInt(e.target.value) || 5 })}
                    />
                  </div>
                  <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end' }}>
                    <label className="form-check">
                      <input
                        type="checkbox"
                        checked={formData.enabled}
                        onChange={e => setFormData({ ...formData, enabled: e.target.checked })}
                      />
                      <span>Enabled</span>
                    </label>
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => { setShowCreateModal(false); setEditingWebhook(null); resetForm(); }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Saving…' : (editingWebhook ? 'Update' : 'Create')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};