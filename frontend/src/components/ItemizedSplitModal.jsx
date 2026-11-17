import React, { useState, useEffect, useMemo } from 'react';
import { API_BASE_URL } from '../services/api';
import { X, Zap, Users, UserCheck, User, CheckCircle2, DollarSign, PieChart } from 'lucide-react';
import { deriveOrderTitle } from '../utils/products';

export default function ItemizedSplitModal({
  isOpen,
  onClose,
  order,
  groceriesGroup,
  currentUser,
  onSplitSaved
}) {
  // Route by the platform the backend reported. The old rule guessed from order-id
  // length, which would have sent short food order ids to the Blinkit endpoint.
  const orderPlatform = String(order?.order_type || '').toUpperCase();
  const isSwiggy = orderPlatform === 'INSTAMART' || orderPlatform.startsWith('SWIGGY');
  const defaultTitle = useMemo(() => {
    const platName = isSwiggy ? 'Swiggy' : 'Blinkit';
    const items = (order && order.item_details && order.item_details.length > 0)
      ? order.item_details
      : (order?.existing_split?.notes_items || []);
    return deriveOrderTitle(platName, items, order?.order_id);
  }, [isSwiggy, order]);

  const [splitMode, setSplitMode] = useState('BILL_LEVEL'); // 'BILL_LEVEL' | 'ITEMIZED'
  const [customTitle, setCustomTitle] = useState('');
  const [buyerId, setBuyerId] = useState(currentUser ? currentUser.id : null);
  
  // Tab 1: Bill Level Options ('ALL' | 'CHOOSE' | 'CUSTOM' | 'SHARES')
  const [billSubMode, setBillSubMode] = useState('ALL');
  const [billAssignedMemberIds, setBillAssignedMemberIds] = useState([]);
  const [customBillAmounts, setCustomBillAmounts] = useState({});
  const [customBillShares, setCustomBillShares] = useState({});
  const [includeInactive, setIncludeInactive] = useState(false);

  // Tab 2: Itemized Products State
  const [itemsState, setItemsState] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const groupMembers = groceriesGroup ? groceriesGroup.members || [] : [];
  const activeMembers = groupMembers.filter(m => m.is_active !== false);
  const inactiveMembers = groupMembers.filter(m => m.is_active === false);
  const effectiveGroupMembers = includeInactive ? groupMembers : (activeMembers.length > 0 ? activeMembers : groupMembers);
  const allMemberIds = effectiveGroupMembers.map(m => m.id);
  const totalAmount = parseFloat(order ? order.total_amount : 0) || 0.0;

  useEffect(() => {
    if (groupMembers.length > 0 && !buyerId) {
      setBuyerId(groupMembers[0].id);
    }
    setBillAssignedMemberIds(allMemberIds);

    // Initialize custom bill amounts equal split defaults (rounded whole rupees, no decimals)
    const initialAmounts = {};
    const equalShare = allMemberIds.length > 0 ? Math.round(totalAmount / allMemberIds.length).toString() : '0';
    allMemberIds.forEach(id => { initialAmounts[id] = equalShare; });
    setCustomBillAmounts(initialAmounts);

    // Initialize custom bill shares with 1 share per member
    const initialShares = {};
    allMemberIds.forEach(id => { initialShares[id] = 1; });
    setCustomBillShares(initialShares);

    if (order && order.item_details && order.item_details.length > 0) {
      const existingItems = order.existing_split ? order.existing_split.notes_items || [] : [];

      const initialItems = order.item_details.map((item, idx) => {
        const matchingSaved = existingItems.find(saved => saved.name === item.name || saved.id === item.id);
        const splitType = matchingSaved ? matchingSaved.split_type || 'ALL' : 'ALL';
        const assignedIds = matchingSaved && matchingSaved.assigned_member_ids ? matchingSaved.assigned_member_ids : allMemberIds;

        return {
          id: idx,
          name: item.name,
          price: parseFloat(item.price) || 0,
          quantity: item.quantity || 1,
          split_type: splitType,
          assigned_ids: assignedIds
        };
      });
      setItemsState(initialItems);
    }
  }, [order, groceriesGroup, includeInactive]);

  if (!isOpen || !order || !groceriesGroup) return null;

  const toggleBillMember = (memberId) => {
    if (billAssignedMemberIds.includes(memberId)) {
      if (billAssignedMemberIds.length === 1) return;
      setBillAssignedMemberIds(billAssignedMemberIds.filter(id => id !== memberId));
    } else {
      setBillAssignedMemberIds([...billAssignedMemberIds, memberId]);
    }
  };

  const handleCustomBillChange = (memberId, value) => {
    setCustomBillAmounts({ ...customBillAmounts, [memberId]: value });
  };

  const activeSelfId = currentUser ? currentUser.id : (buyerId || allMemberIds[0]);

  const setItemMode = (index, mode) => {
    const updated = [...itemsState];
    updated[index].split_type = mode;
    if (mode === 'ALL') {
      updated[index].assigned_ids = allMemberIds;
    } else if (mode === 'PERSONAL') {
      updated[index].assigned_ids = [activeSelfId];
    } else if (mode === 'SPECIFIC') {
      if (!updated[index].assigned_ids || updated[index].assigned_ids.length === 0) {
        updated[index].assigned_ids = allMemberIds;
      }
    }
    setItemsState(updated);
  };

  const toggleItemMember = (index, memberId) => {
    const updated = [...itemsState];
    const currentList = updated[index].assigned_ids || [];
    if (currentList.includes(memberId)) {
      if (currentList.length === 1) return;
      updated[index].assigned_ids = currentList.filter(id => id !== memberId);
    } else {
      updated[index].assigned_ids = [...currentList, memberId];
    }
    setItemsState(updated);
  };

  const round2 = (num) => Math.round((num + Number.EPSILON) * 100) / 100;
  const max1 = (n) => Math.max(1, n);

  const activeBuyerId = buyerId || (currentUser ? currentUser.id : allMemberIds[0]);

  const itemList = itemsState.map(i => ({
    name: i.name,
    price: parseFloat(i.price) || 0,
    split_type: i.split_type,
    assigned_ids: i.split_type === 'ALL'
      ? allMemberIds
      : i.split_type === 'PERSONAL'
        ? [activeBuyerId]
        : (Array.isArray(i.assigned_ids) && i.assigned_ids.length > 0 ? i.assigned_ids : allMemberIds)
  }));

  const sumOfProducts = itemList.reduce((acc, i) => acc + i.price, 0);
  const explicitOtherCharges = parseFloat(order?.other_charges || 0);
  const pooledTaxesAndCharges = explicitOtherCharges > 0
    ? explicitOtherCharges
    : Math.max(0, round2(totalAmount - sumOfProducts));

  const computedFinalOwedMap = {};
  allMemberIds.forEach(id => { computedFinalOwedMap[id] = 0.0; });

  if (splitMode === 'BILL_LEVEL') {
    if (billSubMode === 'ALL') {
      const perPerson = round2(totalAmount / max1(allMemberIds.length));
      allMemberIds.forEach(id => { computedFinalOwedMap[id] = perPerson; });
      const currentSum = Object.values(computedFinalOwedMap).reduce((a, b) => round2(a + b), 0);
      const diff = round2(totalAmount - currentSum);
      if (diff !== 0 && computedFinalOwedMap[activeBuyerId] !== undefined) {
        computedFinalOwedMap[activeBuyerId] = round2(computedFinalOwedMap[activeBuyerId] + diff);
      }
    } else if (billSubMode === 'CHOOSE') {
      const assigned = billAssignedMemberIds.length > 0 ? billAssignedMemberIds : allMemberIds;
      const perPerson = round2(totalAmount / max1(assigned.length));
      assigned.forEach(id => { computedFinalOwedMap[id] = perPerson; });
      const currentSum = Object.values(computedFinalOwedMap).reduce((a, b) => round2(a + b), 0);
      const diff = round2(totalAmount - currentSum);
      if (diff !== 0 && computedFinalOwedMap[activeBuyerId] !== undefined) {
        computedFinalOwedMap[activeBuyerId] = round2(computedFinalOwedMap[activeBuyerId] + diff);
      }
    } else if (billSubMode === 'CUSTOM') {
      allMemberIds.forEach(id => {
        const val = parseFloat(customBillAmounts[id] || 0.0);
        computedFinalOwedMap[id] = isNaN(val) ? 0.0 : val;
      });
      const currentSum = Object.values(computedFinalOwedMap).reduce((a, b) => round2(a + b), 0);
      const diff = round2(totalAmount - currentSum);
      if (diff !== 0 && computedFinalOwedMap[activeBuyerId] !== undefined) {
        computedFinalOwedMap[activeBuyerId] = round2(computedFinalOwedMap[activeBuyerId] + diff);
      }
    } else if (billSubMode === 'SHARES') {
      const assigned = billAssignedMemberIds.length > 0 ? billAssignedMemberIds : allMemberIds;
      const totalUnits = assigned.reduce((sum, id) => sum + (parseFloat(customBillShares[id]) || 0), 0);
      if (totalUnits > 0) {
        let currentSum = 0;
        assigned.forEach(id => {
          const u = parseFloat(customBillShares[id]) || 0;
          const share = round2((totalAmount * u) / totalUnits);
          computedFinalOwedMap[id] = share;
          currentSum = round2(currentSum + share);
        });
        const diff = round2(totalAmount - currentSum);
        if (diff !== 0 && computedFinalOwedMap[activeBuyerId] !== undefined) {
          computedFinalOwedMap[activeBuyerId] = round2(computedFinalOwedMap[activeBuyerId] + diff);
        }
      }
    }
  } else {
    const tempProductSubtotals = {};
    allMemberIds.forEach(id => { tempProductSubtotals[id] = 0.0; });

    itemList.forEach(item => {
      const assigned = item.assigned_ids.length > 0 ? item.assigned_ids : allMemberIds;
      const share = item.price / max1(assigned.length);
      assigned.forEach(id => {
        if (tempProductSubtotals[id] !== undefined) {
          tempProductSubtotals[id] += share;
        }
      });
    });

    const totalSubtotalsSum = Object.values(tempProductSubtotals).reduce((a, b) => a + b, 0);

    if (totalSubtotalsSum <= 0) {
      const equalShare = round2(totalAmount / max1(allMemberIds.length));
      allMemberIds.forEach(id => { computedFinalOwedMap[id] = equalShare; });
      const currentSum = Object.values(computedFinalOwedMap).reduce((a, b) => round2(a + b), 0);
      const diff = round2(totalAmount - currentSum);
      if (diff !== 0 && computedFinalOwedMap[activeBuyerId] !== undefined) {
        computedFinalOwedMap[activeBuyerId] = round2(computedFinalOwedMap[activeBuyerId] + diff);
      }
    } else {
      const netAdjustment = totalAmount - totalSubtotalsSum;
      let calcSum = 0;
      allMemberIds.forEach(id => {
        const sub = tempProductSubtotals[id];
        const adjShare = (sub / totalSubtotalsSum) * netAdjustment;
        const finalVal = Math.max(0, round2(sub + adjShare));
        computedFinalOwedMap[id] = finalVal;
        calcSum = round2(calcSum + finalVal);
      });

      const diff = round2(totalAmount - calcSum);
      if (diff !== 0 && computedFinalOwedMap[activeBuyerId] !== undefined) {
        computedFinalOwedMap[activeBuyerId] = round2(computedFinalOwedMap[activeBuyerId] + diff);
      }
    }
  }

  const handleSaveSplit = async () => {
    try {
      setSubmitting(true);
      setError(null);

      const finalDescription = customTitle.trim() ? customTitle.trim() : defaultTitle;
      const endpoint = isSwiggy ? `${API_BASE_URL}/swiggy/split_order/` : `${API_BASE_URL}/blinkit/split_order/`;

      const payload = {
        group_id: groceriesGroup.id,
        buyer_id: buyerId || (currentUser ? currentUser.id : allMemberIds[0]),
        actor_id: currentUser ? currentUser.id : undefined,
        order_id: String(order.order_id || ''),
        platform: orderPlatform,
        description: finalDescription,
        placed_at: order.placed_at || '',
        total_amount: totalAmount,
        split_mode: splitMode,
        product_names: itemList.map(i => i.name),
        common_fees: pooledTaxesAndCharges,
        bill_split: {
          type: billSubMode,
          member_ids: billAssignedMemberIds,
          custom_amounts: customBillAmounts,
          shares: customBillShares,
          include_inactive: includeInactive
        },
        item_splits: itemList.map(i => ({
          name: i.name,
          price: parseFloat(i.price) || 0,
          split_type: i.split_type,
          assigned_member_ids: i.split_type === 'ALL'
            ? allMemberIds
            : (Array.isArray(i.assigned_ids) && i.assigned_ids.length > 0 ? i.assigned_ids : allMemberIds),
          assigned_names: groupMembers.filter(m => (i.split_type === 'ALL' ? allMemberIds : (i.assigned_ids || [])).includes(m.id)).map(m => m.name.split(' ')[0])
        }))
      };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to split order.');
      }

      onSplitSaved();
      onClose();
    } catch (err) {
      setError(err.message || 'Error saving split.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '600px', maxHeight: '92vh' }}>
        <div className="modal-header">
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Zap size={18} color="var(--accent-primary)" />
              <span>{order.existing_split ? `Re-Split Order #${order.order_id}` : `Split Order #${order.order_id}`}</span>
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Order Bill: ₹{Math.round(totalAmount)} • Group: {groceriesGroup.name}
            </span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ padding: '1rem' }}>
          {error && (
            <div style={{
              padding: '0.5rem 0.75rem',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid var(--color-negative)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--color-negative)',
              fontSize: '0.8rem',
              marginBottom: '0.75rem'
            }}>
              {error}
            </div>
          )}

          {/* Paid By & Custom Expense Title Inputs */}
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.85rem' }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dim)', display: 'block', marginBottom: '0.3rem' }}>
                Paid By:
              </label>
              <select
                className="form-input"
                value={buyerId || activeBuyerId}
                onChange={(e) => setBuyerId(Number(e.target.value))}
                style={{ fontSize: '0.85rem' }}
              >
                {groupMembers.map(m => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>

            <div style={{ flex: 2 }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dim)', display: 'block', marginBottom: '0.3rem' }}>
                Custom Title / Expense Label (Optional):
              </label>
              <input
                type="text"
                className="form-input"
                placeholder={defaultTitle}
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                style={{ fontSize: '0.85rem' }}
              />
            </div>
          </div>

          {/* 2 Main Split Tabs: Tab 1 (Bill Level Split) vs Tab 2 (Product Level Split) */}
          <div className="tab-group" style={{ marginBottom: '1rem' }}>
            <button
              type="button"
              className={`tab-btn ${splitMode === 'BILL_LEVEL' ? 'active' : ''}`}
              onClick={() => setSplitMode('BILL_LEVEL')}
            >
              Bill Level Split
            </button>

            <button
              type="button"
              className={`tab-btn ${splitMode === 'ITEMIZED' ? 'active' : ''}`}
              onClick={() => setSplitMode('ITEMIZED')}
            >
              Product Level Split
            </button>
          </div>

          {/* TAB 1: BILL LEVEL SPLIT OPTIONS */}
          {splitMode === 'BILL_LEVEL' && (
            <div>
              {/* Option to include/exclude inactive members if any exist */}
              {inactiveMembers.length > 0 && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.45rem 0.65rem',
                  backgroundColor: 'rgba(30, 41, 59, 0.5)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: '0.75rem',
                  fontSize: '0.75rem'
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>
                    {inactiveMembers.length} inactive member{inactiveMembers.length > 1 ? 's' : ''} in group ({inactiveMembers.map(m => m.name.split(' ')[0]).join(', ')})
                  </span>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', color: '#ffffff', fontWeight: 600 }}>
                    <input
                      type="checkbox"
                      checked={includeInactive}
                      onChange={(e) => setIncludeInactive(e.target.checked)}
                      style={{ cursor: 'pointer', accentColor: 'var(--accent-primary)' }}
                    />
                    Include inactive
                  </label>
                </div>
              )}

              {/* Sub-modes: Equal (Everyone), Choose People, By Shares, Custom Values */}
              <div style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.85rem' }}>
                <button
                  type="button"
                  className={`btn btn-sm ${billSubMode === 'ALL' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setBillSubMode('ALL')}
                  style={{ fontSize: '0.725rem', flex: 1, padding: '0.3rem 0.4rem' }}
                >
                  <Users size={12} />
                  <span>Equal</span>
                </button>

                <button
                  type="button"
                  className={`btn btn-sm ${billSubMode === 'CHOOSE' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setBillSubMode('CHOOSE')}
                  style={{ fontSize: '0.725rem', flex: 1, padding: '0.3rem 0.4rem' }}
                >
                  <UserCheck size={12} />
                  <span>Choose</span>
                </button>

                <button
                  type="button"
                  className={`btn btn-sm ${billSubMode === 'SHARES' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setBillSubMode('SHARES')}
                  style={{ fontSize: '0.725rem', flex: 1, padding: '0.3rem 0.4rem' }}
                >
                  <PieChart size={12} />
                  <span>By Shares</span>
                </button>

                <button
                  type="button"
                  className={`btn btn-sm ${billSubMode === 'CUSTOM' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setBillSubMode('CUSTOM')}
                  style={{ fontSize: '0.725rem', flex: 1, padding: '0.3rem 0.4rem' }}
                >
                  <DollarSign size={12} />
                  <span>Custom</span>
                </button>
              </div>

              {/* Sub-mode 1: Equal (Everyone) */}
              {billSubMode === 'ALL' && (
                <div className="card" style={{ padding: '0.85rem', marginBottom: '1rem', backgroundColor: 'rgba(30, 41, 59, 0.4)' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.5rem' }}>
                    Total bill of <strong>₹{Math.round(totalAmount)}</strong> will be split equally among all {effectiveGroupMembers.length} group members.
                  </span>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                    ₹{Math.round(totalAmount / max1(effectiveGroupMembers.length))} / person
                  </div>
                </div>
              )}

              {/* Sub-mode 2: Choose People */}
              {billSubMode === 'CHOOSE' && (
                <div className="card" style={{ padding: '0.85rem', marginBottom: '1rem', backgroundColor: 'rgba(30, 41, 59, 0.4)' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600, display: 'block', marginBottom: '0.5rem' }}>
                    Select members to split bill of ₹{Math.round(totalAmount)}:
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.65rem' }}>
                    {groupMembers.map(m => {
                      const isAssigned = billAssignedMemberIds.includes(m.id);
                      return (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => toggleBillMember(m.id)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.3rem',
                            padding: '0.25rem 0.6rem',
                            borderRadius: '9999px',
                            backgroundColor: isAssigned ? 'rgba(16, 185, 129, 0.25)' : 'rgba(15, 23, 42, 0.8)',
                            border: isAssigned ? '1px solid var(--accent-primary)' : '1px solid var(--border-color)',
                            color: isAssigned ? '#ffffff' : 'var(--text-muted)',
                            cursor: 'pointer',
                            fontSize: '0.775rem'
                          }}
                        >
                          <img
                            src={m.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${m.name}`}
                            alt={m.name}
                            style={{ width: '16px', height: '16px', borderRadius: '50%' }}
                          />
                          <span>{m.name.split(' ')[0]}</span>
                          {m.is_active === false && (
                            <span style={{ fontSize: '0.625rem', opacity: 0.7 }}>(Inactive)</span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                    ₹{Math.round(totalAmount / max1(billAssignedMemberIds.length))} / chosen person
                  </div>
                </div>
              )}

              {/* Sub-mode 3: By Shares */}
              {billSubMode === 'SHARES' && (
                <div className="card" style={{ padding: '0.85rem', marginBottom: '1rem', backgroundColor: 'rgba(30, 41, 59, 0.4)' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600, display: 'block', marginBottom: '0.5rem' }}>
                    Enter number of shares for each person (Total: ₹{Math.round(totalAmount)}):
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                    {effectiveGroupMembers.map(m => {
                      const u = parseFloat(customBillShares[m.id]) || 0;
                      const totalUnits = effectiveGroupMembers.reduce((sum, member) => sum + (parseFloat(customBillShares[member.id]) || 0), 0);
                      const approxAmt = totalUnits > 0 ? Math.round((totalAmount * u) / totalUnits) : 0;
                      return (
                        <div key={m.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: '#ffffff' }}>
                            <img
                              src={m.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${m.name}`}
                              alt={m.name}
                              style={{ width: '18px', height: '18px', borderRadius: '50%' }}
                            />
                            <span>{m.name}</span>
                            <span style={{ fontSize: '0.7rem', color: 'var(--accent-primary)', fontWeight: 600 }}>
                              ({approxAmt > 0 ? `₹${approxAmt}` : '₹0'})
                            </span>
                            {m.is_active === false && (
                              <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)', padding: '0.05rem 0.3rem', backgroundColor: 'rgba(148, 163, 184, 0.15)', borderRadius: '3px' }}>
                                Inactive
                              </span>
                            )}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => setCustomBillShares({ ...customBillShares, [m.id]: Math.max(0, u - 1) })}
                              style={{ padding: '0.1rem 0.4rem', fontSize: '0.75rem', minWidth: '22px' }}
                            >
                              -
                            </button>
                            <input
                              type="number"
                              min="0"
                              step="any"
                              className="form-input"
                              style={{ width: '45px', padding: '0.2rem', fontSize: '0.8rem', textAlign: 'center' }}
                              value={customBillShares[m.id] ?? 1}
                              onChange={(e) => setCustomBillShares({ ...customBillShares, [m.id]: Math.max(0, parseFloat(e.target.value) || 0) })}
                            />
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => setCustomBillShares({ ...customBillShares, [m.id]: u + 1 })}
                              style={{ padding: '0.1rem 0.4rem', fontSize: '0.75rem', minWidth: '22px' }}
                            >
                              +
                            </button>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', minWidth: '38px' }}>
                              {u === 1 ? 'share' : 'shares'}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Sub-mode 4: Custom Values / Amounts */}
              {billSubMode === 'CUSTOM' && (
                <div className="card" style={{ padding: '0.85rem', marginBottom: '1rem', backgroundColor: 'rgba(30, 41, 59, 0.4)' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600, display: 'block', marginBottom: '0.5rem' }}>
                    Enter custom exact value/amount for each person (Total: ₹{Math.round(totalAmount)}):
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                    {groupMembers.map(m => (
                      <div key={m.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: '#ffffff' }}>
                          <img
                            src={m.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${m.name}`}
                            alt={m.name}
                            style={{ width: '18px', height: '18px', borderRadius: '50%' }}
                          />
                          <span>{m.name}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>₹</span>
                          <input
                            type="number"
                            step="1"
                            className="form-input"
                            style={{ width: '80px', padding: '0.2rem 0.4rem', fontSize: '0.8rem' }}
                            value={customBillAmounts[m.id] || ''}
                            onChange={(e) => handleCustomBillChange(m.id, e.target.value)}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: PRODUCT LEVEL SPLIT */}
          {splitMode === 'ITEMIZED' && (
            <div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', marginBottom: '0.85rem' }}>
                {itemsState.map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '0.65rem 0.75rem',
                      backgroundColor: 'rgba(30, 41, 59, 0.4)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-color)'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.4rem' }}>
                      <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ffffff' }}>
                        {item.name}
                      </div>

                      <span style={{ fontSize: '0.9rem', fontWeight: 800, color: 'var(--accent-primary)' }}>
                        ₹{Math.round(item.price)}
                      </span>
                    </div>

                    {/* Per Item Split Mode Buttons */}
                    <div style={{ display: 'flex', gap: '0.3rem', marginBottom: item.split_type === 'SPECIFIC' ? '0.5rem' : '0' }}>
                      <button
                        type="button"
                        className={`btn btn-sm ${item.split_type === 'ALL' ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => setItemMode(idx, 'ALL')}
                        style={{ fontSize: '0.725rem', padding: '0.2rem 0.45rem', flex: 1 }}
                      >
                        <Users size={12} />
                        <span>Everyone</span>
                      </button>

                      <button
                        type="button"
                        className={`btn btn-sm ${item.split_type === 'SPECIFIC' ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => setItemMode(idx, 'SPECIFIC')}
                        style={{ fontSize: '0.725rem', padding: '0.2rem 0.45rem', flex: 1 }}
                      >
                        <UserCheck size={12} />
                        <span>Choose People</span>
                      </button>

                      <button
                        type="button"
                        className={`btn btn-sm ${item.split_type === 'PERSONAL' ? 'btn-outline-emerald' : 'btn-secondary'}`}
                        onClick={() => setItemMode(idx, 'PERSONAL')}
                        style={{ fontSize: '0.725rem', padding: '0.2rem 0.45rem', flex: 1 }}
                      >
                        <User size={12} />
                        <span>Personal (Self)</span>
                      </button>
                    </div>

                    {item.split_type === 'SPECIFIC' && (
                      <div style={{
                        padding: '0.45rem',
                        backgroundColor: 'rgba(30, 41, 59, 0.6)',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '0.35rem',
                        marginTop: '0.35rem'
                      }}>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', width: '100%', fontWeight: 600 }}>
                          Split this product among:
                        </span>
                        {groupMembers.map(m => {
                          const isAssigned = (item.assigned_ids || allMemberIds).includes(m.id);
                          return (
                            <button
                              key={m.id}
                              type="button"
                              onClick={() => toggleItemMember(idx, m.id)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.25rem',
                                padding: '0.15rem 0.45rem',
                                borderRadius: '9999px',
                                backgroundColor: isAssigned ? 'rgba(16, 185, 129, 0.25)' : 'rgba(15, 23, 42, 0.8)',
                                border: isAssigned ? '1px solid var(--accent-primary)' : '1px solid var(--border-color)',
                                color: isAssigned ? '#ffffff' : 'var(--text-muted)',
                                cursor: 'pointer',
                                fontSize: '0.725rem'
                              }}
                            >
                              <img
                                src={m.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${m.name}`}
                                alt={m.name}
                                style={{ width: '14px', height: '14px', borderRadius: '50%' }}
                              />
                              <span>{m.name.split(' ')[0]}</span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Single Pooled Taxes & Platform Charges Banner */}
              {pooledTaxesAndCharges > 0 && (
                <div style={{
                  padding: '0.65rem 0.85rem',
                  backgroundColor: 'rgba(245, 158, 11, 0.1)',
                  border: '1px solid rgba(245, 158, 11, 0.25)',
                  borderRadius: 'var(--radius-md)',
                  marginBottom: '0.85rem',
                  fontSize: '0.8rem',
                  color: '#f59e0b',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <CheckCircle2 size={14} color="#f59e0b" />
                    <span>Taxes & Platform Charges (Pooled):</span>
                  </div>
                  <strong>₹{Math.round(pooledTaxesAndCharges)}</strong>
                </div>
              )}
            </div>
          )}

          {/* Live Calculated Share per Person Summary */}
          <div style={{
            padding: '0.75rem',
            backgroundColor: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            borderRadius: 'var(--radius-md)'
          }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--accent-primary)', textTransform: 'uppercase', display: 'block', marginBottom: '0.35rem' }}>
              Final Share:
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {groupMembers.map(m => {
                const amt = computedFinalOwedMap[m.id] || 0.0;
                return (
                  <div
                    key={m.id}
                    style={{
                      fontSize: '0.775rem',
                      backgroundColor: 'rgba(15, 23, 42, 0.8)',
                      border: '1px solid var(--border-color)',
                      padding: '0.2rem 0.5rem',
                      borderRadius: '9999px',
                      color: '#ffffff',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.3rem'
                    }}
                  >
                    <span>{m.name.split(' ')[0]}:</span>
                    <strong style={{ color: amt > 0 ? 'var(--color-positive)' : 'var(--text-dim)' }}>
                      ₹{Math.round(amt)}
                    </strong>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary btn-sm" onClick={handleSaveSplit} disabled={submitting}>
            {submitting ? 'Saving...' : order.existing_split ? 'Update Split' : 'Save Order Split'}
          </button>
        </div>
      </div>
    </div>
  );
}
