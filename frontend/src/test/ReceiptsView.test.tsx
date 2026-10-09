import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ReceiptsView } from '../components/ReceiptsView';
import { api } from '../services/apiClient';
vi.mock('../services/apiClient', () => ({ api: {
  getReceipts: vi.fn(), verifyChain: vi.fn(), verifyReceipt: vi.fn(), exportReceiptMarkdown: vi.fn()
}}));

describe('receipt ledger', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.getReceipts).mockResolvedValue({ total: 0, limit: 50, offset: 0, items: [] });
  });
  it('filters the ledger by search and decision', async () => {
    render(<ReceiptsView />);
    await screen.findByText('No matching receipts in ledger.');
    fireEvent.change(screen.getByLabelText('Search receipts'), { target: { value: 'reviewer-12' } });
    fireEvent.change(screen.getByLabelText('Filter receipt decision'), { target: { value: 'REJECT' } });
    await waitFor(() => expect(api.getReceipts).toHaveBeenLastCalledWith({ search: 'reviewer-12', decision: 'REJECT' }));
    await screen.findByText('No matching receipts in ledger.');
  });
  it('shows chain verification counts and closes the result', async () => {
    vi.mocked(api.verifyChain).mockResolvedValue({ is_valid: true, total_receipts: 3, verified_count: 3, genesis_hash: '0'.repeat(64), head_receipt_hash: 'a'.repeat(64), broken_at_receipt_id: null, details: 'Three receipts verified.' });
    render(<ReceiptsView />);
    fireEvent.click(screen.getByText('Verify Full Audit Chain'));
    expect(await screen.findByText('Three receipts verified.')).toBeInTheDocument();
    expect(screen.getByText('3 / 3')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Close'));
    expect(screen.queryByText('Three receipts verified.')).not.toBeInTheDocument();
  });
  it('does not label a failed chain as verified', async () => {
    vi.mocked(api.verifyChain).mockResolvedValue({ is_valid: false, total_receipts: 3, verified_count: 0, genesis_hash: '0'.repeat(64), head_receipt_hash: null, broken_at_receipt_id: 'r1', details: 'Chain broken at r1.' });
    render(<ReceiptsView />);
    fireEvent.click(screen.getByText('Verify Full Audit Chain'));
    expect(await screen.findByText('✗ Verification Failed')).toBeInTheDocument();
    expect(screen.getByText('See failure details')).toBeInTheDocument();
    expect(screen.queryByText('✓ Verified Intact')).not.toBeInTheDocument();
  });
});
