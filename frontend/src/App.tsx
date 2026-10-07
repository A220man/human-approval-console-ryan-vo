import React, { useState, useEffect } from 'react';
import { ActionItem, UserProfile } from './types/api';
import { api } from './services/apiClient';
import { Navbar } from './components/Navbar';
import { ActionQueue } from './components/ActionQueue';
import { ActionDetailModal } from './components/ActionDetailModal';
import { ReceiptsView } from './components/ReceiptsView';
import { PolicyManager } from './components/PolicyManager';
import { EvaluationDashboard } from './components/EvaluationDashboard';

export const App: React.FC = () => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'queue' | 'receipts' | 'policies' | 'benchmark'>('queue');
  const [selectedAction, setSelectedAction] = useState<ActionItem | null>(null);
  const [queueVersion, setQueueVersion] = useState(0);

  const init = async () => {
    try {
      setLoading(true);
      setUser(await api.getCurrentUser());
    } catch {
      try { setUser(await api.demoLogin('analyst')); }
      catch { setUser(null); }
    } finally { setLoading(false); }
  };

  useEffect(() => { init(); }, []);

  const switchRole = async (r: 'viewer' | 'analyst' | 'admin') => {
    try { setUser(await api.demoLogin(r)); }
    catch (err: any) { alert(err.message); }
  };

  const logout = async () => {
    try { await api.logout(); } catch {}
    setUser(null);
  };

  if (loading) return <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', color: '#9ca3af' }}>Connecting...</div>;

  if (!user) return (
    <div style={{ display: 'flex', minHeight: '100vh', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ maxWidth: '420px', width: '100%', background: '#111827', border: '1px solid #374151', borderRadius: '12px', padding: '2rem', textAlign: 'center' }}>
        <h1 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>Human Approval Console</h1>
        <p style={{ color: '#9ca3af', marginBottom: '1.5rem', fontSize: '0.875rem' }}>Autonomous AI agent human-in-the-loop review</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <button className="btn btn-primary" onClick={() => switchRole('analyst')}>Enter as Analyst</button>
          <button className="btn btn-secondary" onClick={() => switchRole('admin')}>Enter as Admin</button>
          <button className="btn btn-outline" onClick={() => switchRole('viewer')}>Enter as Viewer</button>
        </div>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar user={user} activeTab={tab} onSelectTab={setTab} onSwitchRole={switchRole} onLogout={logout} />
      <main className="container" style={{ flexGrow: 1 }}>
        {tab === 'queue' && <ActionQueue user={user} refreshKey={queueVersion} onSelectAction={setSelectedAction} />}
        {tab === 'receipts' && <ReceiptsView />}
        {tab === 'policies' && <PolicyManager user={user} />}
        {tab === 'benchmark' && <EvaluationDashboard />}
      </main>
      {selectedAction && (
        <ActionDetailModal action={selectedAction} user={user} onClose={() => setSelectedAction(null)} onActionUpdated={() => { setSelectedAction(null); setQueueVersion(v => v + 1); }} />
      )}
    </div>
  );
};
