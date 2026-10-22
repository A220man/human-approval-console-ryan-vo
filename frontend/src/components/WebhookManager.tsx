import React, { useState, useEffect } from 'react';
import { UserProfile, Webhook, WebhookDelivery } from '../types/api';
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

type ViewMode = 'list' | 'deliveries';

export const WebhookManager: React.FC<{ user: UserProfile }> = ({ user }) => {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<Webhook | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [selectedWebhook, setSelectedWebhook] = useState<Webhook | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [deliveriesLoading, setDeliveriesLoading] = useState(false);
  const [deliveriesError, setDeliveriesError] = useState<string | null>(null);
  const [deliveriesPagination, setDeliveriesPagination] = useState({ total: 0, limit: 50, offset: 0 });

  const [formData, setFormData] = useState<WebhookFormData>({
    name: '',
    url: '',
    secret: '',
    event_filter: '',
    enabled: true,
    max_retries: 5,
  });

  const loadWebhooks = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getWebhooks();
      setWebhooks(res.items);
    } catch (err: any) {
      setError(err.message || 'Failed to load webhooks');
    } finally {
      setLoading(false);
    }
  };

  const loadDeliveries = async (webhookId?: string, limit = 50, offset = 0) => {
    try {
      setDeliveriesLoading(true);
      setDeliveriesError(null);
      if (webhookId) {
        const res = await api.getWebhookDeliveriesByWebhook(webhookId, limit, offset);
        setDeliveries(res.items);
        setDeliveriesPagination({ total: res.total, limit: res.limit, offset: res.offset });
        setSelectedWebhook(webhooks.find(w => w.id === webhookId) || null);
      } else {
        const res = await api.getWebhookDeliveries({ limit, offset });
        setDeliveries(res.items);
        setDeliveriesPagination({ total: res.total, limit: res.limit, offset: res.offset });
        setSelectedWebhook(null);
      }
    } catch (err: any) {
      setDeliveriesError(err.message || 'Failed to load delivery history');
    } finally {
      setDeliveriesLoading(false);
    }
  };

  const handleViewDeliveries = (webhook?: Webhook) => {
    setViewMode('deliveries');
    loadDeliveries(webhook?.id);
  };

  const handleBackToList = () => {
    setViewMode('list');
    setSelectedWebhook(null);
    setDeliveries([]);
  };

  const handleDeliveriesPageChange = (offset: number) => {
    const limit = deliveriesPagination.limit;
    const webhookId = selectedWebhook?.id;
    loadDeliveries(webhookId, limit, offset);
  };

  useEffect(() => {
    loadWebhooks();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.url.trim()) return;
    try {
      setSubmitting(true);
      const payload = {
        name: formData.name.trim(),
        url: formData.url.trim(),
        secret: formData.secret.trim() || undefined,
        event_filter: formData.event_filter ? formData.event_filter.split(',').map(s => s.trim()).filter(Boolean) : [],
        enabled: formData.enabled,
        max_retries: formData.max_retries,
      };
      if (editingWebhook) {
        await api.updateWebhook(editingWebhook.id, payload);
      } else {
        await api.createWebhook(payload);
      }
      resetForm();
      setShowCreateModal(false);
      setEditingWebhook(null);
      loadWebhooks();
    } catch (err: any) {
      alert(err.message || 'Failed to save webhook');
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
    if (!confirm(`Delete webhook "${webhook.name}"?`)) return;
    try {
      await api.deleteWebhook(webhook.id);
      loadWebhooks();
    } catch (err: any) {
      alert(err.message || 'Failed to delete webhook');
    }
  };

  const handleTest = async (webhook: Webhook) => {
    try {
      const result = await api.testWebhook(webhook.id);
      alert(result.success ? `Test successful (attempt ${result.attempt})` : `Test failed: ${result.error}`);
      // Refresh deliveries to show the test attempt
      if (viewMode === 'deliveries' && selectedWebhook?.id === webhook.id) {
        loadDeliveries(webhook.id);
      }
    } catch (err: any) {
      alert(err.message || 'Test failed');
    }
  };

  const resetForm = () => {
    setFormData({ name: '', url: '', secret: '', event_filter: '', enabled: true, max_retries: 5 });
  };

  const handleNew = () => {
    setEditingWebhook(null);
    resetForm();
    setShowCreateModal(true);
  };

  const getStatusBadge = (success: boolean | null) => {
    if (success === true) return <span className="badge badge-success">✓ Success</span>;
    if (success === false) return <span className="badge badge-danger">✗ Failed</span>;
    return <span className="badge badge-muted">—</span>;
  };

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  if (loading) {
    return <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>Loading webhooks…</div>;
  }

  const canManage = user.roles.includes('admin');

  if (viewMode === 'deliveries') {
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button className="btn btn-outline" onClick={handleBackToList}>
              ← Back to Webhooks
            </button>
            <h2 style={{ margin: 0 }}>
              Delivery History
              {selectedWebhook && <span style={{ fontWeight: 400, fontSize: '1rem', color: '#9ca3af' }}> — {selectedWebhook.name}</span>}
            </h2>
          </div>
        </div>

        {deliveriesError && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{deliveriesError}</div>}

        <div className="card">
          {deliveries.length === 0 && !deliveriesLoading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#9ca3af' }}>
              <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>No delivery attempts recorded</p>
              <p style={{ fontSize: '0.875rem' }}>
                {selectedWebhook
                  ? 'Send a test webhook or wait for action approvals to generate delivery records.'
                  : 'Configure webhooks and approve actions to see delivery history.'}
              </p>
            </div>
          ) : (
            <>
              {deliveriesLoading && (
                <div style={{ textAlign: 'center', padding: '2rem', color: '#9ca3af' }}>
                  Loading delivery history…
                </div>
              )}
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: '80px' }}>Attempt</th>
                      <th style={{ width: '120px' }}>Status</th>
                      <th>Event</th>
                      <th style={{ width: '150px' }}>Action / Receipt</th>
                      <th style={{ width: '180px' }}>Time (UTC)</th>
                      <th style={{ width: '250px' }}>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deliveries.map((d) => (
                      <tr key={d.id}>
                        <td style={{ fontFamily: 'monospace', fontSize: '0.8125rem' }}>
                          #{d.attempt}
                        </td>
                        <td>{getStatusBadge(d.success)}</td>
                        <td>
                          <span className="badge badge-info" style={{ fontSize: '0.7rem' }}>
                            {d.event_type}
                          </span>
                        </td>
                        <td style={{ fontSize: '0.8125rem', fontFamily: 'monospace' }}>
                          <div>{d.action_id}</div>
                          <div style={{ color: '#9ca3af', fontSize: '0.7rem' }}>{d.receipt_id}</div>
                        </td>
                        <td style={{ fontSize: '0.8125rem', color: '#9ca3af', whiteSpace: 'nowrap' }}>
                          {formatDate(d.created_at)}
                        </td>
                        <td style={{ fontSize: '0.8125rem', maxWidth: '250px' }}>
                          {d.status_code && <span className="badge badge-muted" style={{ marginRight: '0.5rem' }}>HTTP {d.status_code}</span>}
                          {d.error && (
                            <span style={{ color: '#fca5a5', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                              {d.error.length > 80 ? d.error.slice(0, 80) + '…' : d.error}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
                <button
                  className="btn btn-outline"
                  onClick={() => handleDeliveriesPageChange(Math.max(0, deliveriesPagination.offset - deliveriesPagination.limit))}
                  disabled={deliveriesPagination.offset === 0}
                >
                  Previous
                </button>
                <span style={{ display: 'flex', alignItems: 'center', color: '#9ca3af', fontSize: '0.875rem' }}>
                  Showing {deliveriesPagination.offset + 1}–{Math.min(deliveriesPagination.offset + deliveries.length, deliveriesPagination.total)} of {deliveriesPagination.total}
                </span>
                <button
                  className="btn btn-outline"
                  onClick={() => handleDeliveriesPageChange(deliveriesPagination.offset + deliveriesPagination.limit)}
                  disabled={deliveriesPagination.offset + deliveriesPagination.limit >= deliveriesPagination.total}
                >
                  Next
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2 style={{ margin: 0 }}>Webhook Dispatch</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-outline" onClick={() => handleViewDeliveries()}>
            📋 View Delivery History
          </button>
          {canManage && (
            <button className="btn btn-primary" onClick={handleNew}>
              + Add Webhook
            </button>
          )}
        </div>
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
                  <th style={{ width: '160px' }}>Actions</th>
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
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        {canManage && (
                          <>
                            <button className="btn btn-sm btn-outline" onClick={() => handleEdit(wh)} title="Edit">
                              ✎
                            </button>
                            <button className="btn btn-sm btn-outline" onClick={() => handleTest(wh)} title="Test">
                              ▶
                            </button>
                            <button className="btn btn-sm btn-danger" onClick={() => handleDelete(wh)} title="Delete">
                              🗑
                            </button>
                          </>
                        )}
                        <button className="btn btn-sm btn-secondary" onClick={() => handleViewDeliveries(wh)} title="View Deliveries">
                          📋
                        </button>
                      </div>
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