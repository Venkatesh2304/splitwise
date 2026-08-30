import React, { useState } from 'react';
import { api, API_BASE_URL } from '../services/api';
import { Lock, LogIn, Sparkles, User, KeyRound } from 'lucide-react';

export default function LoginScreen({ onLoginSuccess, demoUsers }) {
  const [username, setUsername] = useState('');
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
      
      const res = await fetch(`${API_BASE_URL}/users/login/`, {
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

  const handleSelectDemoUser = (u) => {
    setUsername(u.username);
    setPassword('10');
    setError(null);
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'var(--bg-dark)',
      padding: '1.5rem',
      backgroundImage: 'radial-gradient(circle at 50% 30%, rgba(16, 185, 129, 0.08) 0%, transparent 60%)'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '440px',
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-color)',
        padding: '2rem 1.75rem',
        boxShadow: 'var(--shadow-lg)'
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            width: '3.5rem',
            height: '3.5rem',
            borderRadius: '50%',
            backgroundColor: 'rgba(16, 185, 129, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1rem',
            color: 'var(--accent-primary)',
            border: '1px solid rgba(16, 185, 129, 0.3)'
          }}>
            <Lock size={26} />
          </div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#ffffff', marginBottom: '0.4rem' }}>
            Welcome to Splitwise
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
            Select your profile or enter credentials to sign in
          </p>
        </div>

        {/* Quick User Picker Buttons */}
        {demoUsers && demoUsers.length > 0 && (
          <div style={{ marginBottom: '1.75rem' }}>
            <label className="form-label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem', display: 'block' }}>
              Quick Select Profile:
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: '0.5rem' }}>
              {demoUsers.map((u) => {
                const isSelected = username.toLowerCase() === u.username.toLowerCase();
                return (
                  <button
                    key={u.id || u.username}
                    type="button"
                    onClick={() => handleSelectDemoUser(u)}
                    style={{
                      padding: '0.5rem 0.6rem',
                      borderRadius: 'var(--radius-md)',
                      border: isSelected ? '1px solid var(--accent-primary)' : '1px solid var(--border-color)',
                      backgroundColor: isSelected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(30, 41, 59, 0.5)',
                      color: isSelected ? '#ffffff' : 'var(--text-muted)',
                      fontSize: '0.8rem',
                      fontWeight: isSelected ? 700 : 500,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{
                      width: '1.4rem',
                      height: '1.4rem',
                      borderRadius: '50%',
                      backgroundColor: isSelected ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.1)',
                      color: '#ffffff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.7rem',
                      fontWeight: 700
                    }}>
                      {u.name ? u.name[0].toUpperCase() : u.username[0].toUpperCase()}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', overflow: 'hidden' }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 600 }}>
                        {u.name || u.username}
                      </span>
                      {u.phone_number && (
                        <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)' }}>
                          📱 {u.phone_number}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleLogin}>
          {error && (
            <div style={{
              padding: '0.65rem 0.85rem',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
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
                placeholder="e.g. rahul, akash, venkatesh"
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
            disabled={submitting || !username.trim()}
            style={{
              width: '100%',
              marginTop: '0.5rem',
              padding: '0.75rem',
              fontSize: '0.95rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem'
            }}
          >
            <LogIn size={18} />
            <span>{submitting ? 'Authenticating...' : 'Sign In'}</span>
          </button>
        </form>
      </div>
    </div>
  );
}
