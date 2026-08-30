import React from 'react';
import { LogOut } from 'lucide-react';

export default function Header({
  currentUser,
  activeTab,
  onTabChange,
  onLogout
}) {
  return (
    <header style={{
      backgroundColor: '#0f172a',
      borderBottom: '1px solid rgba(255,255,255,0.08)',
      padding: '0.65rem 1rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      width: '100%'
    }}>
      {/* App Brand */}
      <div
        onClick={() => onTabChange('dashboard')}
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
      >
        <span style={{ fontSize: '1.1rem', fontWeight: 800, color: '#ffffff' }}>
          Splitwise
        </span>
      </div>

      {/* Right Actions: User Profile & Logout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {currentUser && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            backgroundColor: 'rgba(30, 41, 59, 0.8)',
            padding: '0.25rem 0.55rem',
            borderRadius: '9999px',
            fontSize: '0.8rem',
            color: '#ffffff'
          }}>
            <img
              src={currentUser.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${currentUser.name}`}
              alt={currentUser.name}
              style={{ width: '20px', height: '20px', borderRadius: '50%' }}
            />
            <span style={{ fontWeight: 600 }}>{currentUser.name}</span>
          </div>
        )}

        <button
          onClick={onLogout}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '0.25rem 0.4rem',
            display: 'flex',
            alignItems: 'center'
          }}
          title="Switch User / Logout"
        >
          <LogOut size={16} />
        </button>
      </div>
    </header>
  );
}
