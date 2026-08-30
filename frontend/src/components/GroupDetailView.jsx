import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useUser } from '../context/UserContext';
import { ArrowLeft, Plus, HandCoins, Trash2, X } from 'lucide-react';

export default function GroupDetailView({ groupId, onBack, onOpenAddExpense, onOpenSettleUp, currentUser }) {
  const { activeUser } = useUser();
  const [groupData, setGroupData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('expenses'); // 'expenses' | 'breakdown'

  // Selected expense for detailed view modal
  const [selectedExpenseDetails, setSelectedExpenseDetails] = useState(null);
  const [modalTab, setModalTab] = useState('overall'); // 'overall' | 'items'

  const fetchDetail = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getGroupDetail(groupId);
      setGroupData(data);
    } catch (err) {
      console.error(err);
      setError('Failed to load group details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (groupId) {
      fetchDetail();
    }
  }, [groupId]);

  const handleDeleteExpense = async (e, expId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this expense from the group?')) return;
    try {
      await api.deleteExpense(expId);
      if (selectedExpenseDetails && selectedExpenseDetails.id === expId) {
        setSelectedExpenseDetails(null);
      }
      fetchDetail();
    } catch (err) {
      alert('Failed to delete expense.');
    }
  };

  const handleOpenExpenseModal = (exp) => {
    setSelectedExpenseDetails(exp);
    setModalTab('overall');
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
        Loading group...
      </div>
    );
  }

  if (error || !groupData) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem' }}>
        <p style={{ color: 'var(--color-negative)', fontSize: '0.85rem', marginBottom: '1rem' }}>{error || 'Group not found'}</p>
        <button className="btn btn-secondary btn-sm" onClick={onBack}>Back to Dashboard</button>
      </div>
    );
  }

  const currency = groupData.currency || '₹';
  const members = groupData.members || [];
  const expenses = groupData.expenses || [];
  const rawSimplifiedDebts = groupData.simplified_debts || [];
  const netBalances = groupData.net_balances || {};

  const currentAccount = currentUser || activeUser || (members.find(m => m.name.toLowerCase().includes('venkatesh')) || members[0]);
  const myUserId = currentAccount ? currentAccount.id : null;
  const myBalance = myUserId ? (netBalances[myUserId] ?? netBalances[String(myUserId)] ?? 0.0) : 0.0;

  // Filter out any self-debts where debtor and creditor are the same
  const filteredDebts = rawSimplifiedDebts.filter(d => {
    const fromUser = members.find(m => m.id === d.from_user_id) || { name: `User #${d.from_user_id}` };
    const toUser = members.find(m => m.id === d.to_user_id) || { name: `User #${d.to_user_id}` };
    if (d.from_user_id === d.to_user_id) return false;
    if (fromUser.name && toUser.name && fromUser.name.toLowerCase().trim() === toUser.name.toLowerCase().trim()) return false;
    if (d.amount < 0.01) return false;
    return true;
  });

  // Helper to clean title (removes trailing bracketed strings)
  const getCleanTitle = (desc) => {
    if (!desc) return '';
    return desc.replace(/\s*\([^)]*\)$/, '').trim();
  };

  // Format date key for grouping in "30 Aug" format (e.g. 2026-08-30 -> 30 Aug)
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  const formatDateGroupKey = (exp) => {
    if (!exp || !exp.date) return '30 Aug';
    const str = String(exp.date).trim();
    
    // Handle YYYY-MM-DD
    const isoMatch = str.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (isoMatch) {
      const day = parseInt(isoMatch[3], 10);
      const monthIdx = parseInt(isoMatch[2], 10) - 1;
      const monthStr = monthNames[monthIdx] || 'Aug';
      return `${day} ${monthStr}`;
    }

    // Handle "Today, 1:01 pm" or "22 Aug, 12:54 pm"
    if (str.includes(', ')) {
      const datePart = str.split(', ')[0];
      return datePart.replace(/\s*\d{4}\b/g, '').trim();
    }

    const parsedDate = new Date(str);
    if (!isNaN(parsedDate.getTime())) {
      const day = parsedDate.getDate();
      const monthStr = monthNames[parsedDate.getMonth()];
      return `${day} ${monthStr}`;
    }

    return str.replace(/\s*\d{4}\b/g, '').trim() || '30 Aug';
  };

  // Group expenses by date
  const groupedExpenses = {};
  expenses.forEach(exp => {
    const dateKey = formatDateGroupKey(exp);
    if (!groupedExpenses[dateKey]) groupedExpenses[dateKey] = [];
    groupedExpenses[dateKey].push(exp);
  });

  // Helper to parse itemized products out of expense notes or description fallback
  const getExpenseProducts = (exp) => {
    if (!exp) return [];

    if (exp.notes) {
      try {
        const parsed = JSON.parse(exp.notes);
        if (typeof parsed === 'object' && parsed !== null) {
          if (Array.isArray(parsed.items) && parsed.items.length > 0) {
            return parsed.items;
          }
          if (Array.isArray(parsed) && parsed.length > 0) {
            return parsed;
          }
        }
      } catch (e) {
        console.log('Notes is not JSON string:', exp.notes);
      }
    }

    const desc = exp.description || '';
    const match = desc.match(/\((.*?)\)$/);
    if (match && match[1]) {
      const parts = match[1].split(' | ');
      return parts.map(p => {
        const sub = p.split(': ₹');
        return {
          name: sub[0] ? sub[0].trim() : p,
          price: sub[1] ? parseFloat(sub[1]) : 0,
          split_type: 'ALL'
        };
      });
    }

    return [];
  };

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', width: '100%' }}>
      {/* Top Header Navigation */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <button
          onClick={onBack}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-main)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: 600,
            padding: 0
          }}
        >
          <ArrowLeft size={18} />
          <span>Back</span>
        </button>

        <div style={{ display: 'flex', gap: '0.35rem' }}>
          <button className="btn btn-primary btn-sm" onClick={() => onOpenAddExpense(groupData)} style={{ padding: '0.35rem 0.6rem', fontSize: '0.775rem' }}>
            <Plus size={13} />
            <span>Add Expense</span>
          </button>
        </div>
      </div>

      {/* Minimal Group Title & User Balance */}
      <div className="card" style={{ marginBottom: '1rem', padding: '0.85rem 1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.4rem' }}>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#ffffff', lineHeight: 1.2 }}>
              {groupData.name}
            </h2>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.1rem' }}>
              Total Spending: {currency}{groupData.total_spending ? Math.round(groupData.total_spending) : 0}
            </div>
          </div>

          <div>
            {myBalance > 0 ? (
              <div className="balance-tag positive" style={{ fontSize: '0.825rem', padding: '0.3rem 0.75rem' }}>
                You get back {currency}{Math.round(myBalance)}
              </div>
            ) : myBalance < 0 ? (
              <div className="balance-tag negative" style={{ fontSize: '0.825rem', padding: '0.3rem 0.75rem' }}>
                You owe {currency}{Math.round(Math.abs(myBalance))}
              </div>
            ) : (
              <div className="balance-tag neutral" style={{ fontSize: '0.825rem', padding: '0.3rem 0.75rem' }}>
                Settled Up
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tab Switcher: Tab 1 (All Expenses) vs Tab 2 (Breakdown Summary) */}
      <div className="tab-group" style={{ marginBottom: '1rem' }}>
        <button
          className={`tab-btn ${activeTab === 'expenses' ? 'active' : ''}`}
          onClick={() => setActiveTab('expenses')}
        >
          All Expenses ({expenses.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'breakdown' ? 'active' : ''}`}
          onClick={() => setActiveTab('breakdown')}
        >
          Breakdown & Balances
        </button>
      </div>

      {activeTab === 'expenses' ? (
        /* TAB 1: LIST OF EXPENSES GROUPED BY DATE (Clean "28 Aug" format, no icons, no trash button) */
        expenses.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: '0.85rem' }}>No expenses recorded yet.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {Object.entries(groupedExpenses).map(([dateLabel, dateItems]) => (
              <div key={dateLabel}>
                {/* Date Group Header in "28 Aug" format */}
                <div style={{
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  color: 'var(--text-muted)',
                  marginBottom: '0.45rem',
                  paddingLeft: '0.1rem'
                }}>
                  {dateLabel}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                  {dateItems.map((exp) => {
                    const totalAmt = parseFloat(exp.amount) || 0;
                    const payer = exp.created_by || (exp.payers && exp.payers[0] ? exp.payers[0].user : null);
                    const payerName = payer ? (payer.id === myUserId ? 'You' : payer.name.split(' ')[0]) : 'Someone';
                    const myShareObj = exp.shares ? exp.shares.find(s => (s.user_id || s.user?.id) === myUserId) : null;
                    const myOwed = myShareObj ? parseFloat(myShareObj.amount_owed) : 0;

                    return (
                      <div
                        key={exp.id}
                        className="card"
                        style={{ padding: '0.85rem 1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}
                      >
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#ffffff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {getCleanTitle(exp.description)}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.1rem' }}>
                            Paid by <strong style={{ color: '#ffffff' }}>{payerName}</strong>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                          <div style={{ textAlign: 'right', flexShrink: 0 }}>
                            {myOwed > 0 ? (
                              <>
                                <div style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--color-negative)' }}>
                                  {currency}{Math.round(myOwed)}
                                </div>
                                <div style={{ fontSize: '0.725rem', color: 'var(--text-dim)', marginTop: '0.1rem' }}>
                                  Total: {currency}{Math.round(totalAmt)}
                                </div>
                              </>
                            ) : (
                              <>
                                <div style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-dim)' }}>
                                  {currency}0
                                </div>
                                <div style={{ fontSize: '0.725rem', color: 'var(--text-dim)', marginTop: '0.1rem' }}>
                                  Total: {currency}{Math.round(totalAmt)}
                                </div>
                              </>
                            )}
                          </div>

                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleOpenExpenseModal(exp)}
                            style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                          >
                            View
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        /* TAB 2: BREAKDOWN SUMMARY (Members Net Balances & Simplified Debts) */
        <div>
          {/* 1. Member Net Balances Card */}
          <div className="card" style={{ marginBottom: '1rem', padding: '1rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.75rem' }}>
              Member Net Balances
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {members.map((m) => {
                const bal = netBalances[m.id] || 0.0;
                const isMe = m.id === myUserId || (m.name && m.name.toLowerCase().includes('venkatesh'));
                return (
                  <div
                    key={m.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.5rem 0.75rem',
                      backgroundColor: 'rgba(15, 23, 42, 0.6)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-color)'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <img
                        src={m.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${m.name}`}
                        alt={m.name}
                        style={{ width: '24px', height: '24px', borderRadius: '50%' }}
                      />
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#ffffff' }}>
                        {isMe ? `${m.name} (You)` : m.name}
                      </span>
                    </div>

                    <div>
                      {bal > 0 ? (
                        <span className="balance-tag positive" style={{ fontSize: '0.75rem' }}>
                          gets back {currency}{Math.round(bal)}
                        </span>
                      ) : bal < 0 ? (
                        <span className="balance-tag negative" style={{ fontSize: '0.75rem' }}>
                          owes {currency}{Math.round(Math.abs(bal))}
                        </span>
                      ) : (
                        <span className="balance-tag neutral" style={{ fontSize: '0.75rem' }}>
                          settled
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 2. Simplified Settle-Up Transactions */}
          <div className="card" style={{ padding: '1rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.75rem' }}>
              Suggested Settle-Up Payments
            </span>
            {filteredDebts.length === 0 ? (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', textAlign: 'center', padding: '1rem 0' }}>
                Everyone in this group is completely settled up!
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {filteredDebts.map((d, idx) => {
                  const fromUser = members.find(m => m.id === d.from_user_id) || { name: `User #${d.from_user_id}` };
                  const toUser = members.find(m => m.id === d.to_user_id) || { name: `User #${d.to_user_id}` };

                  const fromIsMe = fromUser.id === myUserId || (fromUser.name && fromUser.name.toLowerCase().includes('venkatesh'));
                  const toIsMe = toUser.id === myUserId || (toUser.name && toUser.name.toLowerCase().includes('venkatesh'));

                  if (fromIsMe && toIsMe) return null;

                  const fromName = fromIsMe ? 'You' : fromUser.name.split(' ')[0];
                  const toName = toIsMe ? 'You' : toUser.name.split(' ')[0];

                  return (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.6rem 0.75rem',
                        backgroundColor: 'rgba(15, 23, 42, 0.6)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-color)',
                        fontSize: '0.825rem'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#ffffff' }}>
                        <strong>{fromName}</strong> owes <strong>{toName}</strong>
                      </div>
                      <span style={{ fontWeight: 800, color: 'var(--accent-primary)' }}>
                        {currency}{Math.round(d.amount)}
                      </span>
                    </div>
                  );
                })}

                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => onOpenSettleUp(groupData)}
                  style={{ marginTop: '0.5rem', width: '100%' }}
                >
                  <HandCoins size={14} />
                  <span>Settle Up Debt</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* EXPENSE DETAILS MODAL */}
      {selectedExpenseDetails && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '540px' }}>
            <div className="modal-header">
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#ffffff' }}>
                  Expense Details
                </h3>
              </div>
              <button onClick={() => setSelectedExpenseDetails(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            {/* Modal Internal Tabs Switcher */}
            <div style={{ padding: '0.75rem 1rem 0 1rem' }}>
              <div className="tab-group">
                <button
                  className={`tab-btn ${modalTab === 'overall' ? 'active' : ''}`}
                  onClick={() => setModalTab('overall')}
                >
                  Overall Breakdown
                </button>
                <button
                  className={`tab-btn ${modalTab === 'items' ? 'active' : ''}`}
                  onClick={() => setModalTab('items')}
                >
                  Order Products & Items
                </button>
              </div>
            </div>

            <div className="modal-body" style={{ padding: '1rem' }}>
              {/* TAB 1: OVERALL BREAKDOWN */}
              {modalTab === 'overall' && (
                <div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#ffffff', marginBottom: '0.15rem' }}>
                    {getCleanTitle(selectedExpenseDetails.description)}
                  </div>
                  
                  {/* Order Date badge display */}
                  {(() => {
                    let orderDateDisplay = selectedExpenseDetails.date ? formatDateGroupKey({ date: selectedExpenseDetails.date }) : 'Recent';
                    if (selectedExpenseDetails.notes) {
                      try {
                        const parsedNotes = JSON.parse(selectedExpenseDetails.notes);
                        if (parsedNotes.placed_at) {
                          orderDateDisplay = parsedNotes.placed_at;
                        }
                      } catch(e) {}
                    }
                    return (
                      <div style={{ fontSize: '0.775rem', color: 'var(--text-dim)', marginBottom: '0.5rem' }}>
                        Order Date: <span style={{ color: '#ffffff', fontWeight: 600 }}>{orderDateDisplay}</span>
                      </div>
                    );
                  })()}

                  <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--accent-primary)', marginBottom: '0.85rem' }}>
                    {currency}{Math.round(parseFloat(selectedExpenseDetails.amount))}
                  </div>

                  <div style={{ padding: '0.65rem 0.85rem', backgroundColor: 'rgba(15, 23, 42, 0.6)', borderRadius: 'var(--radius-md)', marginBottom: '1rem', fontSize: '0.825rem' }}>
                    <span style={{ color: 'var(--text-dim)' }}>Paid by: </span>
                    <strong style={{ color: '#ffffff' }}>
                      {selectedExpenseDetails.created_by ? selectedExpenseDetails.created_by.name : 'Group Member'}
                    </strong>
                  </div>

                  <h4 style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                    Member Owed Breakdown:
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    {(selectedExpenseDetails.shares || []).map((s, sIdx) => {
                      const mUser = s.user || members.find(m => m.id === s.user_id) || { name: `Member #${s.user_id}` };
                      const amtOwed = parseFloat(s.amount_owed) || 0;
                      return (
                        <div
                          key={sIdx}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '0.45rem 0.65rem',
                            backgroundColor: 'rgba(30, 41, 59, 0.5)',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.8rem'
                          }}
                        >
                          <div style={{ color: '#ffffff', fontWeight: 600 }}>
                            {mUser.name}
                          </div>
                          <span style={{ color: amtOwed > 0 ? 'var(--color-negative)' : 'var(--text-dim)', fontWeight: 700 }}>
                            {currency}{Math.round(amtOwed)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* TAB 2: ORDER PRODUCTS & ITEM BREAKDOWN */}
              {modalTab === 'items' && (
                <div>
                  <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ffffff', marginBottom: '0.75rem' }}>
                    Itemized Products ({getExpenseProducts(selectedExpenseDetails).length}):
                  </h4>

                  {(() => {
                    const productsList = getExpenseProducts(selectedExpenseDetails);
                    if (productsList.length === 0) {
                      return (
                        <div style={{
                          padding: '1.25rem',
                          backgroundColor: 'rgba(15, 23, 42, 0.6)',
                          borderRadius: 'var(--radius-md)',
                          textAlign: 'center',
                          fontSize: '0.825rem',
                          color: 'var(--text-muted)'
                        }}>
                          Single-bill expense total: ₹{Math.round(parseFloat(selectedExpenseDetails.amount))}.
                        </div>
                      );
                    }

                    const numMembers = Math.max(1, members.length);
                    let totalProductsValue = 0;
                    let mySubtotalProducts = 0;

                    productsList.forEach(p => {
                      const prodValue = p.price || 0;
                      totalProductsValue += prodValue;

                      const splitType = p.split_type || 'ALL';
                      const assignedIds = p.assigned_member_ids || [];

                      if (splitType === 'ALL') {
                        mySubtotalProducts += (prodValue / numMembers);
                      } else if (splitType === 'PERSONAL') {
                        const buyerObj = selectedExpenseDetails.created_by;
                        const buyerId = buyerObj ? (typeof buyerObj === 'object' ? buyerObj.id : buyerObj) : null;
                        const isPersonalForMe = (assignedIds.length > 0 && assignedIds.map(Number).includes(Number(myUserId))) || (Number(buyerId) === Number(myUserId));
                        if (isPersonalForMe) {
                          mySubtotalProducts += prodValue;
                        }
                      } else if (splitType === 'SPECIFIC') {
                        if (assignedIds.length > 0 && assignedIds.map(Number).includes(Number(myUserId))) {
                          mySubtotalProducts += (prodValue / assignedIds.length);
                        } else if (assignedIds.length === 0) {
                          mySubtotalProducts += (prodValue / numMembers);
                        }
                      }
                    });

                    const totalCommonFees = Math.max(0, parseFloat(selectedExpenseDetails.amount) - totalProductsValue);
                    const myFeeShare = totalProductsValue > 0 ? (mySubtotalProducts / totalProductsValue) * totalCommonFees : 0;

                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                        {productsList.map((item, itIdx) => {
                          const prodValue = item.price || 0;
                          const splitType = item.split_type || 'ALL';
                          const assignedIds = item.assigned_member_ids || [];
                          const assignedNames = item.assigned_names || [];

                          let myProductShare = 0;
                          if (splitType === 'ALL') {
                            myProductShare = prodValue / numMembers;
                          } else if (splitType === 'PERSONAL') {
                            const buyerObj = selectedExpenseDetails.created_by;
                            const buyerId = buyerObj ? (typeof buyerObj === 'object' ? buyerObj.id : buyerObj) : null;
                            const isPersonalForMe = (assignedIds.length > 0 && assignedIds.map(Number).includes(Number(myUserId))) || (Number(buyerId) === Number(myUserId));
                            if (isPersonalForMe) {
                              myProductShare = prodValue;
                            }
                          } else if (splitType === 'SPECIFIC') {
                            if (assignedIds.length > 0) {
                              if (assignedIds.map(Number).includes(Number(myUserId))) {
                                myProductShare = prodValue / assignedIds.length;
                              }
                            } else {
                              myProductShare = prodValue / numMembers;
                            }
                          }

                          const isZeroShare = myProductShare === 0;

                          const badgeText = splitType === 'ALL'
                            ? 'Everyone'
                            : splitType === 'PERSONAL'
                            ? `Personal (${selectedExpenseDetails.created_by ? selectedExpenseDetails.created_by.name.split(' ')[0] : 'Self'})`
                            : `Chosen (${assignedNames.length > 0 ? assignedNames.join(', ') : 'Members'})`;

                          return (
                            <div
                              key={itIdx}
                              style={{
                                padding: '0.75rem 0.85rem',
                                backgroundColor: 'rgba(15, 23, 42, 0.6)',
                                border: '1px solid var(--border-color)',
                                borderRadius: 'var(--radius-md)',
                                fontSize: '0.825rem',
                                opacity: isZeroShare ? 0.35 : 1,
                                filter: isZeroShare ? 'grayscale(80%)' : 'none',
                                transition: 'all 0.2s ease'
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                                <div style={{ fontWeight: 700, color: isZeroShare ? 'var(--text-dim)' : '#ffffff' }}>
                                  {item.name}
                                </div>
                                <span className="balance-tag neutral" style={{ fontSize: '0.675rem', padding: '0.15rem 0.45rem' }}>
                                  {badgeText}
                                </span>
                              </div>

                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                <span>Product Value: <strong style={{ color: '#ffffff' }}>{currency}{Math.round(prodValue)}</strong></span>
                                <span>
                                  My Share: <strong style={{ color: isZeroShare ? 'var(--text-dim)' : 'var(--accent-primary)' }}>
                                    {currency}{Math.round(myProductShare)}
                                  </strong>
                                </span>
                              </div>
                            </div>
                          );
                        })}

                        {/* Dedicated My Share of Taxes & Other Charges Row */}
                        {totalCommonFees > 0 && (
                          <div style={{
                            padding: '0.65rem 0.85rem',
                            backgroundColor: 'rgba(245, 158, 11, 0.08)',
                            border: '1px solid rgba(245, 158, 11, 0.25)',
                            borderRadius: 'var(--radius-md)',
                            fontSize: '0.8rem'
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontWeight: 600, color: '#f59e0b' }}>
                              <span>Taxes & Other Charges (My Share)</span>
                              <strong>{currency}{Math.round(myFeeShare)}</strong>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={(e) => handleDeleteExpense(e, selectedExpenseDetails.id)}
                style={{ color: 'var(--color-negative)', border: '1px solid rgba(239, 68, 68, 0.3)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
              >
                <Trash2 size={14} />
                <span>Delete Expense</span>
              </button>

              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedExpenseDetails(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
