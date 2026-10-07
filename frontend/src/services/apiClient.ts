import {
  ActionItem, ActionListResponse, AdvisoryResponse,
  BenchmarkAction, EvaluationMetrics, PolicyItem,
  ReceiptItem, ReceiptVerifyResult, UserProfile
} from '../types/api';

class ApiClient {
  private csrfToken: string | null = null;

  private async fetchCsrf(): Promise<string> {
    if (this.csrfToken) return this.csrfToken;
    try {
      const res = await fetch('/api/auth/csrf', { credentials: 'include' });
      if (res.ok) {
        const d = await res.json();
        this.csrfToken = d.csrf_token || '';
      }
    } catch {}
    return this.csrfToken || '';
  }

  private async request<T>(url: string, opts: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json', ...(opts.headers as Record<string, string> || {}) };
    const method = (opts.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      if (!headers['Content-Type']) headers['Content-Type'] = 'application/json';
      const token = await this.fetchCsrf();
      if (token) headers['x-csrf-token'] = token;
    }

    const res = await fetch(url, { ...opts, headers, credentials: 'include' });
    if (res.status === 401) { this.csrfToken = null; throw new Error('Unauthorized'); }
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        if (err.detail) msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
      } catch {}
      throw new Error(msg);
    }
    return res.status === 204 ? {} as T : res.json();
  }

  getCurrentUser = () => this.request<UserProfile>('/api/auth/me');
  demoLogin = async (role: string) => {
    this.csrfToken = null;
    const u = await this.request<UserProfile>('/api/auth/demo-login', { method: 'POST', body: JSON.stringify({ role }) });
    await this.fetchCsrf();
    return u;
  };
  logout = () => this.request('/api/auth/logout', { method: 'POST' });

  getActions = (p: Record<string, any> = {}) => {
    const qs = new URLSearchParams(Object.entries(p).filter(([_, v]) => v !== undefined).map(([k, v]) => [k, String(v)])).toString();
    return this.request<ActionListResponse>(`/api/actions${qs ? `?${qs}` : ''}`);
  };
  getAction = (id: string) => this.request<ActionItem>(`/api/actions/${id}`);
  ingestAction = (body: any) => this.request<ActionItem>('/api/actions', { method: 'POST', body: JSON.stringify(body) });
  claimAction = (id: string, notes?: string) => this.request<ActionItem>(`/api/actions/${id}/claim`, { method: 'POST', body: JSON.stringify({ notes }) });
  reviewAction = (id: string, body: any) => this.request<any>(`/api/actions/${id}/review`, { method: 'POST', body: JSON.stringify(body) });
  getAdvisory = (id: string) => this.request<AdvisoryResponse>(`/api/actions/${id}/advisory`, { method: 'POST' });

  getReceipts = (limit = 50, offset = 0) => this.request<{ total: number; items: ReceiptItem[] }>(`/api/receipts?limit=${limit}&offset=${offset}`);
  exportReceiptMarkdown = async (id: string) => (await fetch(`/api/receipts/${id}/export`, { credentials: 'include' })).text();
  verifyReceipt = (receipt_id: string) => this.request<ReceiptVerifyResult>('/api/receipts/verify', { method: 'POST', body: JSON.stringify({ receipt_id }) });

  getPolicies = () => this.request<PolicyItem[]>('/api/policies');
  createPolicy = (body: any) => this.request<PolicyItem>('/api/policies', { method: 'POST', body: JSON.stringify(body) });
  deletePolicy = (id: string) => this.request(`/api/policies/${id}`, { method: 'DELETE' });

  getBenchmark = () => this.request<BenchmarkAction[]>('/api/eval/benchmark');
  runEvaluation = () => this.request<EvaluationMetrics>('/api/eval/run', { method: 'POST' });
}

export const api = new ApiClient();
