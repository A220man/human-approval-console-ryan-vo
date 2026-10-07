import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Navbar } from '../components/Navbar';
import { ActionQueue } from '../components/ActionQueue';
import { ActionItem, UserProfile } from '../types/api';

const mockUser: UserProfile = {
  user_id: 'usr-analyst-12345',
  username: 'demo-analyst',
  email: 'analyst@demo.local',
  roles: ['analyst', 'viewer']
};

const mockAction: ActionItem = {
  id: 'act-test-001',
  agent_id: 'test-agent',
  agent_framework: 'langchain',
  session_id: 'sess-1',
  action_type: 'shell_command',
  target_resource: 'prod-server-01',
  payload: { command: 'rm -rf /tmp/test' },
  intent: 'Clean temporary testing files',
  risk_score: 85,
  risk_level: 'high',
  status: 'pending',
  created_at: new Date().toISOString()
};

describe('Frontend UI Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const mockFetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/auth/me')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => mockUser
        });
      }
      if (url.includes('/api/auth/csrf')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ csrf_token: 'test-token' })
        });
      }
      if (url.includes('/api/actions')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            total: 1,
            limit: 50,
            offset: 0,
            stats: {
              pending: 1,
              under_review: 0,
              approved: 0,
              rejected: 0,
              critical_pending: 0
            },
            items: [mockAction]
          })
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({})
      });
    });
    vi.stubGlobal('fetch', mockFetch);
  });

  it('renders console header and navigation tabs', async () => {
    const handleSelectTab = vi.fn();
    const handleSwitchRole = vi.fn();
    const handleLogout = vi.fn();

    render(
      <Navbar
        user={mockUser}
        activeTab="queue"
        onSelectTab={handleSelectTab}
        onSwitchRole={handleSwitchRole}
        onLogout={handleLogout}
      />
    );

    expect(screen.getByText('Approval Console')).toBeInTheDocument();
    expect(screen.getByText('Action Queue')).toBeInTheDocument();
    expect(screen.getByText('Approval Receipts')).toBeInTheDocument();
    expect(screen.getByText('Safety Policies')).toBeInTheDocument();
    expect(screen.getByText('AI Safety Benchmark')).toBeInTheDocument();
    expect(screen.getByText('demo-analyst')).toBeInTheDocument();
  });

  it('renders stats cards and action queue table items', async () => {
    const handleSelectAction = vi.fn();

    render(
      <ActionQueue
        user={mockUser}
        onSelectAction={handleSelectAction}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Pending Review')).toBeInTheDocument();
      expect(screen.getByText('Under Active Review')).toBeInTheDocument();
      expect(screen.getByText('act-test-001')).toBeInTheDocument();
      expect(screen.getByText('Clean temporary testing files')).toBeInTheDocument();
    });
  });

  it('triggers action inspection modal when clicking action item', async () => {
    const handleSelectAction = vi.fn();

    render(
      <ActionQueue
        user={mockUser}
        onSelectAction={handleSelectAction}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Inspect')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Inspect'));
    expect(handleSelectAction).toHaveBeenCalledWith(expect.objectContaining({
      id: 'act-test-001'
    }));
  });
});
