import React, { useState } from 'react';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { X, UserPlus } from 'lucide-react';

export default function AddMemberToGroupModal({ isOpen, onClose, group, onMemberAdded }) {
  const { users } = useUser();
  const [selectedUserId, setSelectedUserId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen || !group) return null;

  const existingMemberIds = (group.members || []).map(m => m.id);
  const nonMembers = users.filter(u => !existingMemberIds.includes(u.id));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedUserId) {
      setError('Please select a member to add.');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      await api.addGroupMember(group.id, parseInt(selectedUserId));
      onMemberAdded();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to add member to group.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '480px' }}>
        <div className="modal-header">
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <UserPlus size={20} color="var(--accent-primary)" />
            <span>Add Member to {group.name}</span>
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

            {nonMembers.length === 0 ? (
              <div style={{ padding: '1rem', textContent: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                All available member personas are already part of this group!
              </div>
            ) : (
              <div className="form-group">
                <label className="form-label">Select Persona to Add</label>
                <select
                  className="form-select"
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                >
                  <option value="">-- Choose Member --</option>
                  {nonMembers.map(u => (
                    <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting || nonMembers.length === 0}>
              {submitting ? 'Adding...' : 'Add to Group'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
