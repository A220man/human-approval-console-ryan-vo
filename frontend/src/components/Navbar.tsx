import React from 'react';
import { UserProfile } from '../types/api';

interface NavbarProps {
  user: UserProfile;
  activeTab: 'queue' | 'receipts' | 'policies' | 'benchmark';
  onSelectTab: (tab: 'queue' | 'receipts' | 'policies' | 'benchmark') => void;
  onSwitchRole: (role: 'viewer' | 'analyst' | 'admin') => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  activeTab,
  onSelectTab,
  onSwitchRole,
  onLogout
}) => {
  return (
    <header className="header">
      <div className="brand">
        <span style={{ fontSize: '1.4rem' }}>🛡️</span>
        <div>
          <span>Approval Console</span>
          <span style={{ fontSize: '0.75rem', color: '#9ca3af', display: 'block', fontWeight: 400 }}>
            AI Agent Human-in-the-Loop Governance
          </span>
        </div>
      </div>

      <nav className="nav-links">
        <button
          className={`nav-btn ${activeTab === 'queue' ? 'active' : ''}`}
          onClick={() => onSelectTab('queue')}
        >
          Action Queue
        </button>
        <button
          className={`nav-btn ${activeTab === 'receipts' ? 'active' : ''}`}
          onClick={() => onSelectTab('receipts')}
        >
          Approval Receipts
        </button>
        <button
          className={`nav-btn ${activeTab === 'policies' ? 'active' : ''}`}
          onClick={() => onSelectTab('policies')}
        >
          Safety Policies
        </button>
        <button
          className={`nav-btn ${activeTab === 'benchmark' ? 'active' : ''}`}
          onClick={() => onSelectTab('benchmark')}
        >
          AI Safety Benchmark
        </button>
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div style={{ textAlign: 'right', fontSize: '0.8rem' }}>
          <div style={{ fontWeight: 600, color: '#f3f4f6' }}>{user.username}</div>
          <div style={{ display: 'flex', gap: '0.25rem', justifyContent: 'flex-end', marginTop: '0.1rem' }}>
            {user.roles.map(r => (
              <span key={r} className="badge badge-low" style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}>
                {r}
              </span>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <select
            className="select-input"
            style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
            onChange={e => onSwitchRole(e.target.value as 'viewer' | 'analyst' | 'admin')}
            value={user.roles.includes('admin') ? 'admin' : user.roles.includes('analyst') ? 'analyst' : 'viewer'}
          >
            <option value="viewer">Role: Viewer</option>
            <option value="analyst">Role: Analyst</option>
            <option value="admin">Role: Admin</option>
          </select>
          <button className="btn btn-outline" style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }} onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>
    </header>
  );
};
