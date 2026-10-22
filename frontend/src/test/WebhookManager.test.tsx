import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { WebhookManager } from '../components/WebhookManager';

// Mock the api client
vi.mock('../services/apiClient', () => ({
  api: {
    getWebhooks: vi.fn(),
    createWebhook: vi.fn(),
    updateWebhook: vi.fn(),
    deleteWebhook: vi.fn(),
    testWebhook: vi.fn(),
    getWebhookDeliveries: vi.fn(),
    getWebhookDeliveriesByWebhook: vi.fn(),
  },
}));

import { api } from '../services/apiClient';

describe('WebhookManager', () => {
  const mockUser = {
    user_id: 'usr-admin-1',
    username: 'admin',
    email: 'admin@test.local',
    roles: ['admin'],
  };

  const mockWebhook = {
    id: 'wh-test-123',
    name: 'Test Webhook',
    url: 'https://example.com/webhook',
    secret: 'secret',
    event_filter: ['action.approved'],
    enabled: true,
    max_retries: 5,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  const mockDelivery = {
    id: 'aud-delivery-1',
    webhook_id: 'wh-test-123',
    webhook_name: 'Test Webhook',
    action_id: 'act-123',
    receipt_id: 'rcpt-123',
    event_type: 'action.approved',
    attempt: 1,
    success: true,
    status_code: 200,
    error: null,
    created_at: '2024-01-01T12:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders webhook list when webhooks exist', async () => {
    (api.getWebhooks as any).mockResolvedValue({ total: 1, items: [mockWebhook] });

    render(<WebhookManager user={mockUser} />);

    await waitFor(() => {
      expect(screen.getByText('Test Webhook')).toBeInTheDocument();
    });
    expect(screen.getByText('https://example.com/webhook')).toBeInTheDocument();
    expect(screen.getByText('Enabled')).toBeInTheDocument();
  });

  it('shows empty state when no webhooks configured', async () => {
    (api.getWebhooks as any).mockResolvedValue({ total: 0, items: [] });

    render(<WebhookManager user={mockUser} />);

    await waitFor(() => {
      expect(screen.getByText('No webhooks configured')).toBeInTheDocument();
    });
  });

  it('shows View Delivery History button for admin', async () => {
    (api.getWebhooks as any).mockResolvedValue({ total: 1, items: [mockWebhook] });

    render(<WebhookManager user={mockUser} />);

    await waitFor(() => {
      expect(screen.getByText((content) => content.includes('View Delivery History'))).toBeInTheDocument();
    });
  });

  it('switches to delivery history view when View Delivery History is clicked', async () => {
    (api.getWebhooks as any).mockResolvedValue({ total: 1, items: [mockWebhook] });
    (api.getWebhookDeliveries as any).mockResolvedValue({ total: 1, limit: 50, offset: 0, items: [mockDelivery] });

    render(<WebhookManager user={mockUser} />);

    await waitFor(() => {
      expect(screen.getByText((content) => content.includes('View Delivery History'))).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText((content) => content.includes('View Delivery History')));

    await waitFor(() => {
      expect(screen.getByText('Delivery History')).toBeInTheDocument();
      expect(screen.getByText('act-123')).toBeInTheDocument();
    });
  });

  it('shows delivery history for specific webhook when clicking delivery icon', async () => {
    (api.getWebhooks as any).mockResolvedValue({ total: 1, items: [mockWebhook] });
    (api.getWebhookDeliveriesByWebhook as any).mockResolvedValue({ total: 1, limit: 50, offset: 0, items: [mockDelivery] });

    render(<WebhookManager user={mockUser} />);

    await waitFor(() => {
      // Find the delivery history button (📋 icon) for the webhook
      const deliveryBtn = screen.getByTitle('View Deliveries');
      fireEvent.click(deliveryBtn);
    });

    await waitFor(() => {
      expect(screen.getByText('Delivery History')).toBeInTheDocument();
      expect(screen.getByText((content) => content.includes('Test Webhook'))).toBeInTheDocument();
      expect(screen.getByText('act-123')).toBeInTheDocument();
    });
  });

  it('displays delivery status badges correctly', async () => {
    (api.getWebhooks as any).mockResolvedValue({ total: 1, items: [mockWebhook] });
    const failedDelivery = { ...mockDelivery, success: false, status_code: 500, error: 'Connection timeout' };
    (api.getWebhookDeliveries as any).mockResolvedValue({ total: 1, limit: 50, offset: 0, items: [failedDelivery] });

    render(<WebhookManager user={mockUser} />);

    await waitFor(() => {
      fireEvent.click(screen.getByText((content) => content.includes('View Delivery History')));
    });

    await waitFor(() => {
      expect(screen.getByText('✗ Failed')).toBeInTheDocument();
      expect(screen.getByText('HTTP 500')).toBeInTheDocument();
    });
  });

  it('shows Back to Webhooks button in delivery view', async () => {
    (api.getWebhooks as any).mockResolvedValue({ total: 1, items: [mockWebhook] });
    (api.getWebhookDeliveries as any).mockResolvedValue({ total: 1, limit: 50, offset: 0, items: [mockDelivery] });

    render(<WebhookManager user={mockUser} />);

    await waitFor(() => {
      fireEvent.click(screen.getByText((content) => content.includes('View Delivery History')));
    });

    await waitFor(() => {
      expect(screen.getByText('← Back to Webhooks')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('← Back to Webhooks'));

    await waitFor(() => {
      expect(screen.getByText('Webhook Dispatch')).toBeInTheDocument();
    });
  });
});