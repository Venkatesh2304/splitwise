import React, { useState } from 'react';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { X, Users, Compass, Home, PartyPopper, Package } from 'lucide-react';

export default function AddGroupModal({ isOpen, onClose, onGroupCreated }) {
  const { users } = useUser();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('TRIP');
  const [currency, setCurrency] = useState('$');
  const [selectedMemberIds, setSelectedMemberIds] = useState(users.map(u => u.id));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const toggleMember = (id) => {
    if (selectedMemberIds.includes(id)) {
      setSelectedMemberIds(selectedMemberIds.filter(mId => mId !== id));
    } else {
      setSelectedMemberIds([...selectedMemberIds, id]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Group name is required.');
      return;
    }
    if (selectedMemberIds.length === 0) {
      setError('Select at least one member for the group.');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const newGroup = await api.createGroup({
        name: name.trim(),
        description: description.trim(),
        category,
        currency,
        member_ids: selectedMemberIds
      });
      onGroupCreated(newGroup);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to create group.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Users size={20} color="var(--accent-primary)" />
            <span>Create New Split Group</span>
          </h3>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
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

            <div className="form-group">
              <label className="form-label">Group Name *</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Goa Trip 2026, Apt 302 Utilities"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
            </div>

            <div className="form-group">
              <label className="form-label">Description</label>
              <input
                type="text"
                className="form-input"
                placeholder="Optional group notes or purpose"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Category</label>
                <select
                  className="form-select"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="TRIP">🏖️ Trip</option>
                  <option value="HOME">🏠 Home / Apartment</option>
                  <option value="EVENT">🎉 Event / Party</option>
                  <option value="OTHER">📦 Other</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Currency Symbol</label>
                <select
                  className="form-select"
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                >
                  <option value="$">$ (USD)</option>
                  <option value="€">€ (EUR)</option>
                  <option value="₹">₹ (INR)</option>
                  <option value="£">£ (GBP)</option>
                </select>
              </div>
            </div>

            {/* Select Group Members */}
            <div className="form-group" style={{ marginTop: '0.5rem' }}>
              <label className="form-label">Select Group Members ({selectedMemberIds.length})</label>
              <div style={{
                maxHeight: '160px',
                overflowY: 'auto',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                padding: '0.5rem',
                backgroundColor: 'rgba(15, 23, 42, 0.4)'
              }}>
                {users.map(u => {
                  const isChecked = selectedMemberIds.includes(u.id);
                  return (
                    <div
                      key={u.id}
                      onClick={() => toggleMember(u.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.5rem 0.75rem',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: isChecked ? 'rgba(16, 185, 129, 0.1)' : 'transparent',
                        cursor: 'pointer',
                        marginBottom: '0.25rem'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <img
                          src={u.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${u.name}`}
                          alt={u.name}
                          className="avatar"
                          style={{ width: '28px', height: '28px' }}
                        />
                        <span style={{ fontSize: '0.9rem', color: '#ffffff', fontWeight: isChecked ? 600 : 400 }}>
                          {u.name}
                        </span>
                      </div>
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => {}}
                        style={{ accentColor: 'var(--accent-primary)', cursor: 'pointer' }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Creating...' : 'Create Group'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
