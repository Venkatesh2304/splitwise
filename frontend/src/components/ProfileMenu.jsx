import React, { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { useUser } from '../context/UserContext';

// Your own details. Only holds the UPI id for now, which is what turns a "you owe Rahul
// ₹340" line into a payment someone can actually make.
export default function ProfileMenu({ currentUser, onLogout }) {
  const { refreshUsers } = useUser();
  const [open, setOpen] = useState(false);
  const [upiId, setUpiId] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [position, setPosition] = useState({ top: 44, right: 12, width: 280 });
  const wrapRef = useRef(null);
  const buttonRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  const toggle = async () => {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const width = Math.min(280, window.innerWidth - 24);
      const right = Math.max(12, Math.min(window.innerWidth - rect.right, window.innerWidth - width - 12));
      setPosition({ top: rect.bottom + 8, right, width });
      setMessage(null);
      if (!loaded) {
        try {
          const { upi_id: saved } = await api.getUpiId(currentUser.id);
          setUpiId(saved || '');
        } catch {
          // leave the field empty; saving still works
        }
        setLoaded(true);
      }
    }
    setOpen(!open);
  };

  const save = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await api.updateUser(currentUser.id, { upi_id: upiId.trim() });
      await refreshUsers();
      setMessage({ ok: true, text: upiId.trim() ? 'Saved. People can now pay you from the app.' : 'Removed.' });
    } catch (err) {
      setMessage({ ok: false, text: err.message || 'Could not save that.' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <span ref={wrapRef} style={{ position: 'relative', display: 'flex' }}>
      <button
        ref={buttonRef}
        onClick={toggle}
        title="Your details"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.35rem',
          backgroundColor: 'rgba(30, 41, 59, 0.8)',
          border: 'none',
          padding: '0.25rem 0.55rem',
          borderRadius: '9999px',
          fontSize: '0.8rem',
          color: '#ffffff',
          cursor: 'pointer'
        }}
      >
        <img
          src={currentUser.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${currentUser.name}`}
          alt={currentUser.name}
          style={{ width: '20px', height: '20px', borderRadius: '50%' }}
        />
        <span style={{ fontWeight: 600 }}>{currentUser.name.split(' ')[0]}</span>
      </button>

      {open && (
        <div style={{
          position: 'fixed',
          top: position.top,
          right: position.right,
          width: position.width,
          maxWidth: 'none',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow-md)',
          padding: '0.85rem',
          fontSize: '0.8rem',
          zIndex: 60
        }}>
          <div style={{ fontWeight: 700, marginBottom: '0.15rem' }}>{currentUser.name}</div>
          <div style={{ color: 'var(--text-dim)', marginBottom: '0.7rem' }}>
            @{currentUser.username || currentUser.id}
          </div>

          <label className="form-label" style={{ fontSize: '0.75rem' }}>Your UPI ID</label>
          <input
            className="form-input"
            placeholder="yourname@okhdfcbank"
            value={upiId}
            onChange={(e) => setUpiId(e.target.value)}
            style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
          />
          <div style={{ color: 'var(--text-dim)', marginTop: '0.35rem', lineHeight: 1.4 }}>
            Lets the others pay you from the app — it opens their UPI app with the amount filled in.
          </div>

          {message && (
            <p style={{ marginTop: '0.5rem', color: message.ok ? 'var(--accent-primary)' : 'var(--color-negative)' }}>
              {message.text}
            </p>
          )}

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.7rem' }}>
            <button className="btn btn-primary btn-sm" onClick={save} disabled={busy}>
              {busy ? 'Saving…' : 'Save'}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setOpen(false); onLogout(); }}>
              Switch user
            </button>
          </div>
        </div>
      )}
    </span>
  );
}
