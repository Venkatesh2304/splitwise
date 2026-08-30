import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { X, HandCoins, ArrowRight } from 'lucide-react';

export default function SettleUpModal({ isOpen, onClose, group, initialPayerId, initialPayeeId, initialAmount, onSettlementRecorded }) {
  const [payerId, setPayerId] = useState('');
  const [payeeId, setPayeeId] = useState('');
  const [amount, setAmount] = useState('');
  const [notes, setNotes] = useState('Payment settlement via Splitwise');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const members = group ? group.members || [] : [];

  useEffect(() => {
    if (members.length >= 2) {
      setPayerId(initialPayerId ? String(initialPayerId) : String(members[0].id));
      setPayeeId(initialPayeeId ? String(initialPayeeId) : String(members[1].id));
      setAmount(initialAmount ? String(initialAmount) : '');
    }
  }, [group, initialPayerId, initialPayeeId, initialAmount]);

  if (!isOpen || !group) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!amount || parseFloat(amount) <= 0) {
      setError('Settlement amount must be greater than zero.');
      return;
    }
    if (payerId === payeeId) {
      setError('Payer and payee must be different members.');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      await api.createSettlement({
        group_id: group.id,
        payer_id: parseInt(payerId),
        payee_id: parseInt(payeeId),
        amount: parseFloat(amount),
        date,
        notes: notes.trim()
      });
      onSettlementRecorded();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to record settlement.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '520px' }}>
        <div className="modal-header">
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <HandCoins size={20} color="var(--accent-primary)" />
            <span>Settle Up Balance</span>
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div style={{
                padding: '0.75rem 1rem',
                backgroundColor: 'var(--bg-negative-light)',
                border: '1px solid var(--color-negative)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--color-negative)',
                fontSize: '0.85rem',
                marginBottom: '1.25rem'
              }}>
                {error}
              </div>
            )}

            {/* Payer to Payee Flow */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto 1fr',
              gap: '0.75rem',
              alignItems: 'center',
              marginBottom: '1.25rem',
              padding: '1rem',
              backgroundColor: 'rgba(15, 23, 42, 0.6)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)'
            }}>
              <div>
                <label className="form-label" style={{ fontSize: '0.75rem' }}>Payer (Who Paid)</label>
                <select className="form-select" value={payerId} onChange={(e) => setPayerId(e.target.value)}>
                  {members.map(m => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))}
                </select>
              </div>

              <div style={{ marginTop: '1.25rem' }}>
                <ArrowRight size={20} color="var(--accent-primary)" />
              </div>

              <div>
                <label className="form-label" style={{ fontSize: '0.75rem' }}>Payee (Recipient)</label>
                <select className="form-select" value={payeeId} onChange={(e) => setPayeeId(e.target.value)}>
                  {members.map(m => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Settlement Amount ({group.currency || '$'}) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="form-input"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label className="form-label">Date</label>
                <input
                  type="date"
                  className="form-input"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Notes</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Venmo transfer, cash payment"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Recording...' : 'Record Payment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
