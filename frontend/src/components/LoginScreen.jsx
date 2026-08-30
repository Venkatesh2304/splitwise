import React, { useState } from 'react';
import { api } from '../services/api';
import { Lock, LogIn, Sparkles, User, KeyRound } from 'lucide-react';

export default function LoginScreen({ onLoginSuccess, demoUsers }) {
  const [username, setUsername] = useState('venkatesh');
  const [password, setPassword] = useState('10');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username.trim()) {
      setError('Please select or enter a username.');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      
      const res = await fetch('http://localhost:8000/api/users/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password: password.trim() })
      });
      
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Login failed.');
      }
      
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || 'Failed to authenticate.');
    } finally {
      setSubmitting(false);
    }
  };

  const handlePickAvatar = (userObj) => {
    setUsername(userObj.username || userObj.name.toLowerCase());
    setPassword('10');
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#0f172a',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1.5rem',
      background: 'radial-gradient(circle at 50% 30%, rgba(16, 185, 129, 0.12), transparent 70%)'
    }}>
      <div className="card" style={{
        width: '100%',
        maxWidth: '440px',
        padding: '2.25rem 2rem',
        borderRadius: 'var(--radius-xl)',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)'
      }}>
        {/* Branding Header */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            width: '54px',
            height: '54px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #10b981, #06b6d4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1rem auto',
            boxShadow: '0 8px 24px rgba(16, 185, 129, 0.35)'
          }}>
            <Sparkles size={28} color="#ffffff" />
          </div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#ffffff', marginBottom: '0.35rem' }}>
            Splitwise + Blinkit
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Sign in to manage splitwise groups & split Blinkit grocery bills.
          </p>
        </div>

        {/* Demo Persona Quick Selectors */}
        <div style={{ marginBottom: '1.5rem' }}>
          <label className="form-label" style={{ textAlign: 'center', display: 'block', marginBottom: '0.65rem' }}>
            Quick Select Account
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.6rem' }}>
            {(demoUsers || []).map(u => {
              const uName = u.username || u.name.toLowerCase();
              const isSelected = username.toLowerCase() === uName.toLowerCase();
              return (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => handlePickAvatar(u)}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '0.35rem',
                    padding: '0.6rem 0.3rem',
                    backgroundColor: isSelected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(30, 41, 59, 0.6)',
                    border: isSelected ? '2px solid var(--accent-primary)' : '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-md)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <img
                    src={u.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${u.name}`}
                    alt={u.name}
                    className="avatar"
                    style={{ width: '32px', height: '32px' }}
                  />
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: isSelected ? '#ffffff' : 'var(--text-muted)' }}>
                    {u.name.split(' ')[0]}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <form onSubmit={handleLogin}>
          {error && (
            <div style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--bg-negative-light)',
              border: '1px solid var(--color-negative)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--color-negative)',
              fontSize: '0.85rem',
              marginBottom: '1.25rem',
              textAlign: 'center'
            }}>
              {error}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Username</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. venkatesh, alex, sarah"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
              <User size={18} color="var(--text-dim)" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Password (Default: 10)</label>
            <div style={{ position: 'relative' }}>
              <input
                type="password"
                className="form-input"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
              <KeyRound size={18} color="var(--text-dim)" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting}
            style={{ width: '100%', marginTop: '0.5rem', padding: '0.85rem' }}
          >
            <LogIn size={18} />
            <span>{submitting ? 'Authenticating...' : 'Sign In to Splitwise'}</span>
          </button>
        </form>
      </div>
    </div>
  );
}
