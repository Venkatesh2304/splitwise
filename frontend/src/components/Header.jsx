import React from 'react';
import { LogOut } from 'lucide-react';
import NotificationBell from './NotificationBell';
import ProfileMenu from './ProfileMenu';

export default function Header({
  currentUser,
  activeTab,
  onTabChange,
  onLogout,
  pushState,
  onEnablePush,
  onDisablePush,
  onTestPush
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

      {/* Right Actions: Notifications, User Profile & Logout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {currentUser && (
          <NotificationBell
            state={pushState}
            onEnable={onEnablePush}
            onDisable={onDisablePush}
            onTest={onTestPush}
          />
        )}

        {currentUser && <ProfileMenu currentUser={currentUser} onLogout={onLogout} />}

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
