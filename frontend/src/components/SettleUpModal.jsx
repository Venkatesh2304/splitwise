import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useUser } from '../context/UserContext';
import { X, HandCoins, ArrowRight, Smartphone, Copy, Check } from 'lucide-react';
import { canOpenUpiApp, upiPayLink } from '../utils/upi';

export default function SettleUpModal({ isOpen, onClose, group, initialPayerId, initialPayeeId, initialAmount, onSettlementRecorded }) {
  const { activeUser } = useUser();
  const [payerId, setPayerId] = useState('');
  const [payeeId, setPayeeId] = useState('');
  const [amount, setAmount] = useState('');
  const [notes, setNotes] = useState('Payment settlement via Splitwise');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [payeeUpi, setPayeeUpi] = useState({ loading: false, upiId: '', name: '' });
  const [copiedUpi, setCopiedUpi] = useState(false);
  const [upiInfoMsg, setUpiInfoMsg] = useState(null);

  const members = group ? group.members || [] : [];

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    setUpiInfoMsg(null);
    if (members.length >= 2) {
      // Default: you are paying someone else
      const me = activeUser && members.find(m => m.id === activeUser.id);
      const defaultPayer = me || members[0];
      const defaultPayee = members.find(m => m.id !== defaultPayer.id);
      setPayerId(initialPayerId ? String(initialPayerId) : String(defaultPayer.id));
      setPayeeId(initialPayeeId ? String(initialPayeeId) : String(defaultPayee.id));
      setAmount(initialAmount ? String(initialAmount) : '');
    }
  }, [isOpen, group, initialPayerId, initialPayeeId, initialAmount]);

  useEffect(() => {
    if (!isOpen || !payeeId) {
      setPayeeUpi({ loading: false, upiId: '', name: '' });
      return;
    }
    let cancelled = false;
    setPayeeUpi(prev => ({ ...prev, loading: true }));
    api.getUpiId(payeeId)
      .then(res => {
        if (!cancelled) {
          setPayeeUpi({
            loading: false,
            upiId: res?.upi_id || '',
            name: res?.name || ''
          });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPayeeUpi({ loading: false, upiId: '', name: '' });
        }
      });
    return () => { cancelled = true; };
  }, [isOpen, payeeId]);

  if (!isOpen || !group) return null;

  const handlePayViaUpi = () => {
    setError(null);
    setUpiInfoMsg(null);
    const numAmount = parseFloat(amount);
    if (!amount || isNaN(numAmount) || numAmount <= 0) {
      setError('Settlement amount must be greater than zero.');
      return;
    }
    if (payerId === payeeId) {
      setError('Payer and payee must be different members.');
      return;
    }
    if (!payeeUpi.upiId) {
      const payeeName = members.find(m => String(m.id) === String(payeeId))?.name || 'Payee';
      setError(`${payeeName} does not have a UPI ID configured.`);
      return;
    }

    const payeeMember = members.find(m => String(m.id) === String(payeeId));
    const recipientName = payeeUpi.name || (payeeMember ? payeeMember.name : '');
    const link = upiPayLink({
      upiId: payeeUpi.upiId,
      name: recipientName,
      amount: numAmount,
      note: notes.trim() || `${group.name} settle-up`
    });

    if (canOpenUpiApp()) {
      setUpiInfoMsg({
        type: 'success',
        text: `UPI app opened for ${group.currency || '₹'}${numAmount.toFixed(2)}. Once you complete payment in your UPI app, click "Record Payment" below to save.`
      });
      window.location.href = link;
    } else {
      navigator.clipboard?.writeText(payeeUpi.upiId);
      setCopiedUpi(true);
      setTimeout(() => setCopiedUpi(false), 2500);
      setUpiInfoMsg({
        type: 'info',
        text: `UPI app links only open on a mobile phone. Copied ${payeeUpi.upiId} to clipboard to pay ${group.currency || '₹'}${numAmount.toFixed(2)}.`
      });
    }
  };

  const handleSubmit = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
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
        notes: notes.trim(),
        actor_id: activeUser ? activeUser.id : undefined
      });
      onSettlementRecorded();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to record settlement.');
    } finally {
      setSubmitting(false);
    }
  };

  const selectedPayee = members.find(m => String(m.id) === String(payeeId));
  const payeeDisplayName = selectedPayee ? selectedPayee.name : 'Payee';

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

            {upiInfoMsg && (
              <div style={{
                padding: '0.75rem 1rem',
                backgroundColor: upiInfoMsg.type === 'success' ? 'var(--bg-positive-light)' : 'rgba(30, 41, 59, 0.7)',
                border: `1px solid ${upiInfoMsg.type === 'success' ? 'var(--color-positive)' : 'var(--border-color)'}`,
                borderRadius: 'var(--radius-md)',
                color: upiInfoMsg.type === 'success' ? '#10b981' : '#cbd5e1',
                fontSize: '0.825rem',
                marginBottom: '1.25rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '0.5rem'
              }}>
                <span>{upiInfoMsg.text}</span>
                <button
                  type="button"
                  onClick={() => setUpiInfoMsg(null)}
                  style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', padding: 0 }}
                >
                  <X size={15} />
                </button>
              </div>
            )}

            {/* Payer to Payee Flow */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto 1fr',
              gap: '0.75rem',
              alignItems: 'center',
              marginBottom: '1rem',
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

            {/* Payee UPI Status info card */}
            {payeeId && (
              payeeUpi.upiId ? (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.65rem 0.85rem',
                  backgroundColor: 'rgba(16, 185, 129, 0.08)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  borderRadius: 'var(--radius-md)',
                  marginBottom: '1.25rem',
                  gap: '0.5rem'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                    <Smartphone size={18} color="var(--accent-primary)" style={{ flexShrink: 0 }} />
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: '0.675rem', color: 'var(--accent-primary)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        {payeeDisplayName}'s UPI ID
                      </div>
                      <div style={{ fontSize: '0.825rem', color: '#ffffff', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {payeeUpi.upiId}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      navigator.clipboard?.writeText(payeeUpi.upiId);
                      setCopiedUpi(true);
                      setTimeout(() => setCopiedUpi(false), 2000);
                    }}
                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', gap: '0.25rem', flexShrink: 0 }}
                    title="Copy UPI ID"
                  >
                    {copiedUpi ? (
                      <>
                        <Check size={13} color="var(--accent-primary)" />
                        <span style={{ color: 'var(--accent-primary)' }}>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy size={13} />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
              ) : (
                !payeeUpi.loading && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    padding: '0.5rem 0.75rem',
                    backgroundColor: 'rgba(15, 23, 42, 0.4)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-md)',
                    marginBottom: '1.25rem',
                    fontSize: '0.75rem',
                    color: 'var(--text-dim)'
                  }}>
                    <span>ℹ️ {payeeDisplayName} has not set up a UPI ID yet.</span>
                  </div>
                )
              )
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Settlement Amount ({group.currency || '₹'}) *</label>
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
                placeholder="e.g. Venmo transfer, cash payment, UPI"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>

          <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              {Boolean(payeeUpi.upiId) && (
                <button
                  type="button"
                  className="btn btn-outline-emerald"
                  onClick={handlePayViaUpi}
                  disabled={submitting || !amount || parseFloat(amount) <= 0}
                  title="Pay this edited amount via UPI (GPay, PhonePe, Paytm)"
                  style={{ fontWeight: 700 }}
                >
                  <Smartphone size={16} />
                  <span>
                    Pay {group.currency || '₹'}{amount && !isNaN(parseFloat(amount)) ? Math.round(parseFloat(amount)) : ''} via UPI
                  </span>
                </button>
              )}
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? 'Recording...' : 'Record Payment'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
