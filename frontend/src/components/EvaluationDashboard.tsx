import React, { useState, useEffect } from 'react';
import { BenchmarkAction, EvaluationMetrics } from '../types/api';
import { api } from '../services/apiClient';

export const EvaluationDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<EvaluationMetrics | null>(null);
  const [samples, setSamples] = useState<BenchmarkAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true); setError(null);
      const [m, b] = await Promise.all([api.runEvaluation(), api.getBenchmark()]);
      setMetrics(m); setSamples(b);
    } catch (err: any) { setError(err.message || 'Evaluation failed'); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadData(); }, []);

  const handleRun = async () => {
    try {
      setEvaluating(true);
      const m = await api.runEvaluation(); setMetrics(m);
    } catch (err: any) { alert(err.message); }
    finally { setEvaluating(false); }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2>AI Agent Safety Benchmark Evaluation</h2>
          <p style={{ fontSize: '0.85rem', color: '#9ca3af' }}>Empirical evaluation of risk classification against ground-truth actions.</p>
        </div>
        <button className="btn btn-primary" onClick={handleRun} disabled={evaluating}>
          {evaluating ? 'Evaluating...' : 'Re-Run Evaluation'}
        </button>
      </div>

      {loading ? <div style={{ textAlign: 'center', padding: '3rem', color: '#9ca3af' }}>Running benchmark...</div>
      : error ? <div style={{ padding: '1rem', background: '#7f1d1d', borderRadius: '8px', color: '#fecaca' }}>{error}</div>
      : metrics && (
        <div>
          <div className="stats-grid">
            {[
              { l: 'Accuracy', v: `${(metrics.accuracy * 100).toFixed(1)}%`, c: '#38bdf8' },
              { l: 'Precision (Destructive)', v: `${(metrics.precision * 100).toFixed(1)}%`, c: '#34d399' },
              { l: 'Recall (Destructive)', v: `${(metrics.recall * 100).toFixed(1)}%`, c: '#fbbf24' },
              { l: 'F1-Score', v: `${(metrics.f1_score * 100).toFixed(1)}%`, c: '#c084fc' },
              { l: 'Critical False Negatives', v: `${(metrics.critical_false_negative_rate * 100).toFixed(1)}%`, c: metrics.critical_false_negative_rate === 0 ? '#34d399' : '#f87171' }
            ].map(s => <div key={s.l} className="stat-card"><div className="label">{s.l}</div><div className="value" style={{ color: s.c }}>{s.v}</div></div>)}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem', marginBottom: '1.25rem' }}>
            <div style={{ background: '#111827', border: '1px solid #374151', borderRadius: '8px', padding: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>Confusion Matrix</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', textAlign: 'center' }}>
                <div style={{ background: '#064e3b', padding: '0.5rem', borderRadius: '4px' }}><div style={{ fontSize: '0.7rem' }}>TP</div><strong>{metrics.confusion_matrix.true_positives}</strong></div>
                <div style={{ background: '#1e293b', padding: '0.5rem', borderRadius: '4px' }}><div style={{ fontSize: '0.7rem' }}>FP</div><strong>{metrics.confusion_matrix.false_positives}</strong></div>
                <div style={{ background: '#1e293b', padding: '0.5rem', borderRadius: '4px' }}><div style={{ fontSize: '0.7rem' }}>FN</div><strong>{metrics.confusion_matrix.false_negatives}</strong></div>
                <div style={{ background: '#064e3b', padding: '0.5rem', borderRadius: '4px' }}><div style={{ fontSize: '0.7rem' }}>TN</div><strong>{metrics.confusion_matrix.true_negatives}</strong></div>
              </div>
            </div>

            <div style={{ background: '#111827', border: '1px solid #374151', borderRadius: '8px', padding: '1rem' }}>
              <h3 style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>Category Breakdown</h3>
              <div className="table-container">
                <table>
                  <thead><tr><th>Category</th><th>Samples</th><th>Accuracy</th><th>FN</th></tr></thead>
                  <tbody>
                    {Object.entries(metrics.breakdown_by_category).map(([cat, info]) => (
                      <tr key={cat}>
                        <td><strong>{cat}</strong></td><td>{info.total}</td>
                        <td style={{ color: info.accuracy >= 0.8 ? '#34d399' : '#fbbf24', fontWeight: 600 }}>{(info.accuracy * 100).toFixed(1)}%</td>
                        <td>{info.false_negatives}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div>
            <h3 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>Benchmark Actions Dataset ({samples.length})</h3>
            <div className="table-container">
              <table>
                <thead><tr><th>ID</th><th>Category</th><th>Type</th><th>Target</th><th>Ground Truth</th></tr></thead>
                <tbody>
                  {samples.map(s => (
                    <tr key={s.id}>
                      <td style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>{s.id}</td>
                      <td><span style={{ fontSize: '0.75rem', background: '#1e293b', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>{s.category}</span></td>
                      <td style={{ fontSize: '0.8rem' }}>{s.action_type}</td>
                      <td style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>{s.target_resource}</td>
                      <td><span className={`badge ${s.ground_truth_destructive ? 'badge-high' : 'badge-low'}`}>{s.ground_truth_destructive ? 'Destructive' : 'Benign'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
