import React, { useState, useEffect } from 'react';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { X, Receipt, Calculator, Check, AlertCircle } from 'lucide-react';

export default function AddExpenseModal({ isOpen, onClose, groups, activeGroup, onExpenseAdded }) {
  const { activeUser } = useUser();

  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('FOOD');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [paidById, setPaidById] = useState('');
  const [splitType, setSplitType] = useState('EQUAL'); // 'EQUAL' | 'EXACT' | 'PERCENTAGE'
  
  // Custom split values: { [userId]: amountOrPercentage }
  const [customValues, setCustomValues] = useState({});
  const [selectedSplitMemberIds, setSelectedSplitMemberIds] = useState([]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const currentGroup = groups.find(g => String(g.id) === String(selectedGroupId)) || activeGroup || (groups.length > 0 ? groups[0] : null);
  const groupMembers = currentGroup ? currentGroup.members || [] : [];

  useEffect(() => {
    if (activeGroup) {
      setSelectedGroupId(String(activeGroup.id));
    } else if (groups.length > 0 && !selectedGroupId) {
      setSelectedGroupId(String(groups[0].id));
    }
  }, [activeGroup, groups]);

  useEffect(() => {
    if (groupMembers.length > 0) {
      const allIds = groupMembers.map(m => m.id);
      setSelectedSplitMemberIds(allIds);

      // Default paidBy to activeUser if member, otherwise first member
      if (activeUser && allIds.includes(activeUser.id)) {
        setPaidById(String(activeUser.id));
      } else {
        setPaidById(String(allIds[0]));
      }

      // Initialize default equal percentages / exacts
      const initialCustom = {};
      const equalPct = (100 / allIds.length).toFixed(2);
      allIds.forEach(id => {
        initialCustom[id] = equalPct;
      });
      setCustomValues(initialCustom);
    }
  }, [selectedGroupId, currentGroup]);

  if (!isOpen) return null;

  const totalAmountNum = parseFloat(amount) || 0;

  // Custom split validation status
  let splitValidationMsg = null;
  if (splitType === 'EXACT') {
    const exactSum = selectedSplitMemberIds.reduce((sum, id) => sum + (parseFloat(customValues[id]) || 0), 0);
    const diff = Math.abs(exactSum - totalAmountNum);
    if (diff > 0.01 && totalAmountNum > 0) {
      splitValidationMsg = `Exact shares sum to $${exactSum.toFixed(2)}, but total amount is $${totalAmountNum.toFixed(2)}. (${exactSum < totalAmountNum ? 'Short by $' + (totalAmountNum - exactSum).toFixed(2) : 'Over by $' + (exactSum - totalAmountNum).toFixed(2)})`;
    }
  } else if (splitType === 'PERCENTAGE') {
    const pctSum = selectedSplitMemberIds.reduce((sum, id) => sum + (parseFloat(customValues[id]) || 0), 0);
    const diff = Math.abs(pctSum - 100);
    if (diff > 0.01) {
      splitValidationMsg = `Percentages sum to ${pctSum.toFixed(2)}%, but must equal 100%.`;
    }
  }

  const toggleSplitMember = (id) => {
    if (selectedSplitMemberIds.includes(id)) {
      if (selectedSplitMemberIds.length === 1) return; // Must have at least 1
      setSelectedSplitMemberIds(selectedSplitMemberIds.filter(mId => mId !== id));
    } else {
      setSelectedSplitMemberIds([...selectedSplitMemberIds, id]);
    }
  };

  const handleCustomValueChange = (userId, val) => {
    setCustomValues({
      ...customValues,
      [userId]: val
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!description.trim()) {
      setError('Description is required.');
      return;
    }
    if (!amount || totalAmountNum <= 0) {
      setError('Expense amount must be greater than 0.');
      return;
    }
    if (!currentGroup) {
      setError('Please select a group.');
      return;
    }
    if (splitValidationMsg) {
      setError(splitValidationMsg);
      return;
    }

    // Build payload
    const payers = [
      {
        user_id: parseInt(paidById),
        amount_paid: totalAmountNum
      }
    ];

    const shares = selectedSplitMemberIds.map(uid => {
      const item = { user_id: uid };
      if (splitType === 'EXACT') {
        item.amount_owed = parseFloat(customValues[uid]) || 0;
      } else if (splitType === 'PERCENTAGE') {
        item.percentage = parseFloat(customValues[uid]) || 0;
      }
      return item;
    });

    try {
      setSubmitting(true);
      setError(null);

      await api.createExpense({
        group_id: currentGroup.id,
        description: description.trim(),
        amount: totalAmountNum,
        category,
        split_type: splitType,
        created_by_id: activeUser ? activeUser.id : parseInt(paidById),
        date,
        payers,
        shares
      });

      onExpenseAdded();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to create expense.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '620px' }}>
        <div className="modal-header">
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Receipt size={20} color="var(--accent-primary)" />
            <span>Add Group Expense</span>
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

            {/* Group Selection */}
            <div className="form-group">
              <label className="form-label">Split Group</label>
              <select
                className="form-select"
                value={selectedGroupId}
                onChange={(e) => setSelectedGroupId(e.target.value)}
              >
                {groups.map(g => (
                  <option key={g.id} value={g.id}>
                    {g.name} ({g.currency || '$'})
                  </option>
                ))}
              </select>
            </div>

            {/* Expense Description & Amount Row */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Expense Description *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Dinner, Uber ride, Grocery bill"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label className="form-label">Amount ({currentGroup ? currentGroup.currency : '$'}) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="form-input"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </div>
            </div>

            {/* Category, Date & Paid By */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.85rem' }}>
              <div className="form-group">
                <label className="form-label">Category</label>
                <select className="form-select" value={category} onChange={(e) => setCategory(e.target.value)}>
                  <option value="FOOD">🍔 Food & Dining</option>
                  <option value="UTILITIES">💡 Utilities & Bills</option>
                  <option value="TRANSPORT">🚗 Transport</option>
                  <option value="ENTERTAINMENT">🎟️ Entertainment</option>
                  <option value="SHOPPING">🛍️ Shopping</option>
                  <option value="OTHER">📦 Other</option>
                </select>
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

              <div className="form-group">
                <label className="form-label">Paid By</label>
                <select className="form-select" value={paidById} onChange={(e) => setPaidById(e.target.value)}>
                  {groupMembers.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Split Mode Selector */}
            <div style={{ marginTop: '1rem', marginBottom: '0.85rem' }}>
              <label className="form-label">Split Options</label>
              <div className="tab-group">
                <button
                  type="button"
                  className={`tab-btn ${splitType === 'EQUAL' ? 'active' : ''}`}
                  onClick={() => setSplitType('EQUAL')}
                >
                  Split Equally
                </button>
                <button
                  type="button"
                  className={`tab-btn ${splitType === 'EXACT' ? 'active' : ''}`}
                  onClick={() => setSplitType('EXACT')}
                >
                  Exact Amounts
                </button>
                <button
                  type="button"
                  className={`tab-btn ${splitType === 'PERCENTAGE' ? 'active' : ''}`}
                  onClick={() => setSplitType('PERCENTAGE')}
                >
                  By Percentages (%)
                </button>
              </div>
            </div>

            {/* Split Participants Breakdown List */}
            <div style={{
              backgroundColor: 'rgba(15, 23, 42, 0.5)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md)',
              padding: '0.85rem',
              maxHeight: '180px',
              overflowY: 'auto'
            }}>
              {splitValidationMsg && (
                <div style={{ fontSize: '0.8rem', color: 'var(--color-negative)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <AlertCircle size={14} />
                  <span>{splitValidationMsg}</span>
                </div>
              )}

              {groupMembers.map(m => {
                const isSelected = selectedSplitMemberIds.includes(m.id);
                const equalShare = totalAmountNum > 0 && selectedSplitMemberIds.length > 0 && isSelected
                  ? (totalAmountNum / selectedSplitMemberIds.length).toFixed(2)
                  : '0.00';

                return (
                  <div
                    key={m.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.45rem 0.65rem',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: isSelected ? 'rgba(30, 41, 59, 0.8)' : 'transparent',
                      marginBottom: '0.25rem'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSplitMember(m.id)}
                        style={{ accentColor: 'var(--accent-primary)', cursor: 'pointer' }}
                      />
                      <img
                        src={m.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${m.name}`}
                        alt={m.name}
                        className="avatar"
                        style={{ width: '26px', height: '26px' }}
                      />
                      <span style={{ fontSize: '0.875rem', color: '#ffffff', opacity: isSelected ? 1 : 0.5 }}>
                        {m.name}
                      </span>
                    </div>

                    <div>
                      {splitType === 'EQUAL' && isSelected && (
                        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                          {currentGroup ? currentGroup.currency : '$'}{equalShare}
                        </span>
                      )}

                      {splitType === 'EXACT' && isSelected && (
                        <input
                          type="number"
                          step="0.01"
                          className="form-input"
                          style={{ width: '100px', padding: '0.3rem 0.5rem', fontSize: '0.85rem' }}
                          placeholder="0.00"
                          value={customValues[m.id] || ''}
                          onChange={(e) => handleCustomValueChange(m.id, e.target.value)}
                        />
                      )}

                      {splitType === 'PERCENTAGE' && isSelected && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <input
                            type="number"
                            step="0.1"
                            className="form-input"
                            style={{ width: '75px', padding: '0.3rem 0.5rem', fontSize: '0.85rem' }}
                            placeholder="0"
                            value={customValues[m.id] || ''}
                            onChange={(e) => handleCustomValueChange(m.id, e.target.value)}
                          />
                          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>%</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : 'Save Expense'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
