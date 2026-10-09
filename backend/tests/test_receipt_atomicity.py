"""Receipt failures cannot commit a decision without its proof."""
import json
import pytest
from app.core.database import get_connection
from app.services.receipt_service import ReceiptService


def approve(client):
    return client.post('/api/actions/act-demo-002/review', json={
        'decision': 'APPROVE', 'rationale': 'Checked compatibility before approval.'})


def test_receipt_failure_rolls_back_decision(analyst_client, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('injected storage failure')
    monkeypatch.setattr(ReceiptService, 'create_receipt', fail)
    with pytest.raises(RuntimeError, match='injected storage failure'):
        approve(analyst_client)
    row = get_connection().execute("SELECT status, rationale FROM actions WHERE id='act-demo-002'").fetchone()
    assert row['status'] == 'pending'
    assert row['rationale'] is None
    assert get_connection().execute('SELECT COUNT(*) FROM receipts').fetchone()[0] == 0


def test_chain_head_is_read_under_write_transaction(analyst_client, monkeypatch):
    original = ReceiptService.get_latest_receipt_hash
    def guarded():
        assert get_connection().in_transaction, 'chain head must be read after reserving the writer lock'
        return original()
    monkeypatch.setattr(ReceiptService, 'get_latest_receipt_hash', guarded)
    assert approve(analyst_client).status_code == 200
    assert analyst_client.post('/api/receipts/verify-chain').json()['is_valid'] is True


def test_exported_manifest_tampering_is_detected(analyst_client):
    rid = approve(analyst_client).json()['receipt']['receipt_id']
    conn = get_connection()
    record = conn.execute('SELECT receipt_data_json FROM receipts WHERE id=?', (rid,)).fetchone()
    data = json.loads(record[0]); data['decision'] = 'REJECT'
    conn.execute('UPDATE receipts SET receipt_data_json=? WHERE id=?', (json.dumps(data),rid)); conn.commit()
    assert analyst_client.post('/api/receipts/verify', json={'receipt_id':rid}).json()['is_valid'] is False
    assert analyst_client.post('/api/receipts/verify-chain').json()['is_valid'] is False


def test_concurrent_reviews_produce_one_decision_and_receipt(analyst_client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(2)
    def request():
        barrier.wait(timeout=5)
        return approve(analyst_client).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert sorted(results) == [200, 400]
    conn = get_connection()
    assert conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0] == 1
    result = analyst_client.post('/api/receipts/verify-chain').json()
    assert result['is_valid'] is True
    assert result['verified_count'] == 1


def test_receipt_search_filters_and_pagination(analyst_client):
    rid = approve(analyst_client).json()['receipt']['receipt_id']
    matching = analyst_client.get('/api/receipts', params={'decision':'APPROVE','search':'act-demo-002'}).json()
    assert matching['total'] == 1
    assert matching['items'][0]['id'] == rid
    assert analyst_client.get('/api/receipts', params={'decision':'REJECT'}).json()['total'] == 0
    assert analyst_client.get('/api/receipts', params={'search':"' OR 1=1 --"}).json()['total'] == 0
    beyond = analyst_client.get('/api/receipts', params={'limit':1,'offset':1}).json()
    assert beyond['total'] == 1 and beyond['items'] == []
    assert analyst_client.get('/api/receipts', params={'limit':101}).status_code == 422


def test_empty_chain_and_missing_csrf(viewer_client):
    result = viewer_client.post('/api/receipts/verify-chain').json()
    assert result['is_valid'] is True and result['total_receipts'] == 0
    viewer_client.headers.pop('x-csrf-token')
    assert viewer_client.post('/api/receipts/verify-chain').status_code == 403
