import React from 'react';
import { LayoutDashboard, Plus, Users, Compass, Home, PartyPopper, Package } from 'lucide-react';

const categoryIcons = {
  TRIP: <Compass size={18} color="#06b6d4" />,
  HOME: <Home size={18} color="#10b981" />,
  EVENT: <PartyPopper size={18} color="#8b5cf6" />,
  OTHER: <Package size={18} color="#f59e0b" />
};

export default function Sidebar({ groups, activeGroupId, onSelectGroup, onSelectDashboard, onOpenAddGroup }) {
  return (
    <aside className="sidebar-layout">
      {/* Dashboard Link */}
      <button
        onClick={onSelectDashboard}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '0.75rem 1rem',
          borderRadius: 'var(--radius-md)',
          backgroundColor: activeGroupId === null ? 'var(--bg-surface-hover)' : 'transparent',
          color: activeGroupId === null ? 'var(--accent-primary)' : 'var(--text-muted)',
          border: 'none',
          cursor: 'pointer',
          fontWeight: 600,
          fontSize: '0.925rem',
          textAlign: 'left',
          marginBottom: '1.5rem',
          transition: 'all 0.2s ease'
        }}
      >
        <LayoutDashboard size={20} />
        <span>Dashboard Overview</span>
      </button>

      {/* Groups Section Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 0.5rem 0.5rem 0.5rem',
        borderBottom: '1px solid var(--border-color)',
        marginBottom: '0.75rem'
      }}>
        <span style={{
          fontSize: '0.75rem',
          fontWeight: 700,
          color: 'var(--text-dim)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em'
        }}>
          My Groups ({groups.length})
        </span>
        <button
          onClick={onOpenAddGroup}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--accent-primary)',
            cursor: 'pointer',
            padding: '2px',
            display: 'flex',
            alignItems: 'center'
          }}
          title="Create New Group"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* Groups List */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        {groups.length === 0 ? (
          <div style={{ padding: '1rem 0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            No groups created yet. Click + to create one!
          </div>
        ) : (
          groups.map(group => {
            const isActive = activeGroupId === group.id;
            return (
              <button
                key={group.id}
                onClick={() => onSelectGroup(group.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '0.7rem 0.85rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: isActive ? 'rgba(16, 185, 129, 0.12)' : 'transparent',
                  border: isActive ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid transparent',
                  color: isActive ? '#ffffff' : 'var(--text-muted)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  {categoryIcons[group.category] || categoryIcons.OTHER}
                </div>
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{
                    fontSize: '0.875rem',
                    fontWeight: isActive ? 700 : 500,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}>
                    {group.name}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                    {group.members ? group.members.length : 0} members
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
