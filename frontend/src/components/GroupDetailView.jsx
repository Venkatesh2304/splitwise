import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useUser } from '../context/UserContext';
import { ArrowLeft, Plus, HandCoins, Trash2, X, Pencil, ChevronRight, Sparkles } from 'lucide-react';

const isAfter = (iso, baseline) => Boolean(iso && baseline) && new Date(iso) > new Date(baseline);

// A UPI app can only be opened from a phone; elsewhere we show the id to copy instead
const canOpenUpiApp = () => /Android|iPhone|iPad/i.test(navigator.userAgent) || navigator.maxTouchPoints > 1;

function upiPayLink({ upiId, name, amount, note }) {
  const params = new URLSearchParams({
    pa: upiId,
    pn: name || '',
    am: Number(amount).toFixed(2),
    cu: 'INR',
    tn: note || 'Splitwise settle-up',
  });
  return `upi://pay?${params.toString()}`;
}

const userIdOf = (row) => (row && row.user && row.user.id) ?? (row ? row.user_id : null);
const firstName = (user) => (user && user.name ? user.name.split(' ')[0] : 'Someone');

// Whole rupees like the rest of the app, but never show a real amount as "0"
const shortAmount = (n) => {
  const abs = Math.abs(n);
  return Math.round(abs) > 0 ? Math.round(abs) : abs.toFixed(2);
};

function relativeTime(iso) {
  if (!iso) return '';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const secs = (Date.now() - then.getTime()) / 1000;
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  if (secs < 2 * 86400) return 'yesterday';
  if (secs < 7 * 86400) return `${Math.floor(secs / 86400)}d ago`;
  return then.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function isGrocerySplit(exp) {
  try {
    const notes = JSON.parse(exp.notes || '');
    return Boolean(notes && notes.platform);
  } catch {
    return false;
  }
}

// Who actually paid (not who typed it in)
function payersOf(exp) {
  return (exp.payers || []).filter(p => (parseFloat(p.amount_paid) || 0) > 0);
}

function payerSummary(exp, myUserId, members) {
  const payers = payersOf(exp);
  if (payers.length === 0) return exp.created_by ? (exp.created_by.id === myUserId ? 'You' : firstName(exp.created_by)) : 'Someone';
  const firstId = userIdOf(payers[0]);
  const name = firstId === myUserId ? 'You' : firstName(payers[0].user || members.find(m => m.id === firstId));
  return payers.length > 1 ? `${name} & ${payers.length - 1} other${payers.length > 2 ? 's' : ''}` : name;
}

// What this expense means for me: paid minus my share
function myPosition(exp, myUserId) {
  const paid = payersOf(exp).filter(p => userIdOf(p) === myUserId).reduce((sum, p) => sum + (parseFloat(p.amount_paid) || 0), 0);
  const share = (exp.shares || []).find(sh => userIdOf(sh) === myUserId);
  const owed = share ? parseFloat(share.amount_owed) || 0 : 0;
  return { paid, owed, net: paid - owed, involved: paid > 0.005 || owed > 0.005 };
}

function NewBadge({ label = 'New' }) {
  return (
    <span style={{
      marginLeft: '0.4rem',
      fontSize: '0.625rem',
      fontWeight: 800,
      textTransform: 'uppercase',
      letterSpacing: '0.03em',
      color: 'var(--accent-primary)',
      backgroundColor: 'var(--bg-positive-light)',
      border: '1px solid rgba(16, 185, 129, 0.35)',
      borderRadius: '999px',
      padding: '0.05rem 0.35rem',
      verticalAlign: 'middle'
    }}>
      {label}
    </span>
  );
}

function addedLine(item, myUserId) {
  const who = (u) => (u && u.id === myUserId ? 'you' : firstName(u));
  const parts = [];
  if (item.created_by) parts.push(`${item.kind === 'settlement' ? 'Recorded' : 'Added'} by ${who(item.created_by)}`);
  if (item.created_at) parts.push(relativeTime(item.created_at));
  if (item.updated_at) parts.push(item.updated_by ? `edited by ${who(item.updated_by)}` : 'edited');
  return parts.filter(Boolean).join(' · ');
}

export default function GroupDetailView({
  groupId,
  onBack,
  onOpenAddExpense,
  onOpenSettleUp,
  onOpenBlinkit,
  onEditExpense,
  currentUser,
  seenBaseline,
  onGroupOpened,
  refreshToken = 0,
  focusExpenseId = null,
  onFocusHandled
}) {
  const { activeUser } = useUser();
  const [groupData, setGroupData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('expenses'); // 'expenses' | 'breakdown'

  // Selected expense for detailed view modal
  const [selectedExpenseDetails, setSelectedExpenseDetails] = useState(null);
  const [modalTab, setModalTab] = useState('overall'); // 'overall' | 'items'
  const [selectedSettlement, setSelectedSettlement] = useState(null);
  const [stripDismissed, setStripDismissed] = useState(false);
  const [payInfo, setPayInfo] = useState(null);       // shown on desktop, where upi:// does nothing
  const [nudgeState, setNudgeState] = useState({});   // "debtor-creditor" -> message

  const actorId = (currentUser || activeUser)?.id;

  // Only the first load shows "Loading…"; refreshes swap the data in place
  const fetchDetail = async () => {
    try {
      setError(null);
      const data = await api.getGroupDetail(groupId, actorId);
      setGroupData(data);
      // Hand the baseline up on the first load; App keeps it fixed for this visit
      if (onGroupOpened) onGroupOpened(groupId, data.last_seen_at);
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
  }, [groupId, refreshToken]);

  // Keep an open detail modal in step with fresh data; open the expense a notification pointed at
  useEffect(() => {
    if (!groupData) return;
    const expenses = groupData.expenses || [];
    setSelectedExpenseDetails(current => (current ? expenses.find(e => e.id === current.id) || null : current));
    if (focusExpenseId) {
      const target = expenses.find(e => e.id === focusExpenseId);
      if (target) {
        setActiveTab('expenses');
        setSelectedExpenseDetails(target);
        setModalTab('overall');
      }
      if (onFocusHandled) onFocusHandled();
    }
  }, [groupData, focusExpenseId]);

  const handleDeleteExpense = async (e, expId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this expense from the group?')) return;
    try {
      await api.deleteExpense(expId, actorId);
      if (selectedExpenseDetails && selectedExpenseDetails.id === expId) {
        setSelectedExpenseDetails(null);
      }
      fetchDetail();
    } catch (err) {
      alert('Failed to delete expense.');
    }
  };

  // Open the payee's UPI app with the amount filled in, and leave the settle form ready
  // for when they come back — nothing tells us whether the payment actually happened.
  const handlePay = async (payee, amount) => {
    try {
      const { upi_id: upiId, name } = await api.getUpiId(payee.id);
      if (!upiId) {
        setPayInfo({ name: payee.name, text: `${payee.name.split(' ')[0]} hasn't added a UPI ID yet.` });
        return;
      }
      const link = upiPayLink({ upiId, name, amount, note: `${groupData.name} settle-up` });
      if (canOpenUpiApp()) {
        onOpenSettleUp(groupData, actorId, payee.id, Number(amount).toFixed(2));
        window.location.href = link;
      } else {
        setPayInfo({ name: payee.name, text: `Pay ${payee.name.split(' ')[0]} at ${upiId} — UPI apps only open on a phone.` });
      }
    } catch (err) {
      setPayInfo({ name: payee.name, text: 'Could not fetch their UPI ID.' });
    }
  };

  // Keyed per row: the same person can owe several people, and the reply belongs to the
  // row that was tapped
  const handleNudge = async (debtor, amount, rowKey) => {
    setNudgeState(current => ({ ...current, [rowKey]: 'Sending…' }));
    try {
      await api.nudge({ actorId, userId: debtor.id, groupId: groupData.id, amount });
      setNudgeState(current => ({ ...current, [rowKey]: `Asked ${debtor.name.split(' ')[0]} to settle up.` }));
    } catch (err) {
      setNudgeState(current => ({ ...current, [rowKey]: err.message.replace(/^\{"error":"|"\}$/g, '') }));
    }
  };

  const handleDeleteSettlement = async (settlementId) => {
    if (!window.confirm('Delete this settle-up payment? Balances will go back to how they were before it.')) return;
    try {
      await api.deleteSettlement(settlementId, actorId);
      setSelectedSettlement(null);
      fetchDetail();
    } catch (err) {
      alert('Failed to delete payment.');
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

  const currentAccount = currentUser || activeUser || members[0];
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

  // One timeline: expenses and settle-up payments, newest first, grouped by date
  const settlements = groupData.settlements || [];
  const activity = [
    ...expenses.map(exp => ({ ...exp, kind: 'expense' })),
    ...settlements.map(st => ({ ...st, kind: 'settlement' }))
  ].sort((a, b) => {
    const byDate = String(b.date || '').localeCompare(String(a.date || ''));
    return byDate !== 0 ? byDate : String(b.created_at || '').localeCompare(String(a.created_at || ''));
  });

  const groupedActivity = {};
  activity.forEach(item => {
    const dateKey = formatDateGroupKey(item);
    if (!groupedActivity[dateKey]) groupedActivity[dateKey] = [];
    groupedActivity[dateKey].push(item);
  });

  // Everything recorded since this person last opened the group. Deletions only exist
  // here — their row is gone — so the strip is the only place they can be shown.
  const missedEvents = (groupData.activity || []).filter(e => isAfter(e.created_at, seenBaseline));
  const isNew = (item) => isAfter(item.created_at, seenBaseline);
  const isUpdated = (item) => !isNew(item) && isAfter(item.updated_at, seenBaseline);

  const memberName = (user, id) => {
    const uid = user ? user.id : id;
    if (uid === myUserId) return 'You';
    return firstName(user || members.find(m => m.id === uid));
  };

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
          Activity ({activity.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'breakdown' ? 'active' : ''}`}
          onClick={() => setActiveTab('breakdown')}
        >
          Breakdown & Balances
        </button>
      </div>

      {activeTab === 'expenses' && missedEvents.length > 0 && !stripDismissed && (
        <div className="card" style={{ marginBottom: '1rem', padding: '0.85rem 1rem', borderLeft: '4px solid var(--accent-primary)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.6rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', minWidth: 0 }}>
              <Sparkles size={16} color="var(--accent-primary)" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#ffffff' }}>
                {missedEvents.length} {missedEvents.length === 1 ? 'change' : 'changes'} since you were last here
              </span>
            </div>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setStripDismissed(true)}
              style={{ padding: '0.2rem 0.55rem', fontSize: '0.7rem', flexShrink: 0 }}
            >
              Mark as seen
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
            {missedEvents.map(event => {
              const gone = event.kind === 'expense_deleted' || event.kind === 'settlement_deleted';
              return (
                <div
                  key={event.id}
                  onClick={() => {
                    const target = expenses.find(e => e.id === event.expense_id);
                    if (target) handleOpenExpenseModal(target);
                  }}
                  style={{
                    padding: '0.5rem 0.65rem',
                    backgroundColor: 'rgba(15, 23, 42, 0.6)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    cursor: event.expense_id && !gone ? 'pointer' : 'default',
                    opacity: gone ? 0.75 : 1
                  }}
                >
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#ffffff', textDecoration: gone ? 'line-through' : 'none' }}>
                    {event.title}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.1rem' }}>
                    {[event.line, relativeTime(event.created_at)].filter(Boolean).join(' · ')}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {activeTab === 'expenses' ? (
        /* TAB 1: ACTIVITY — expenses and settle-ups grouped by date ("28 Aug") */
        activity.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: '0.85rem' }}>No expenses recorded yet.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {Object.entries(groupedActivity).map(([dateLabel, dateItems]) => (
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
                  {dateItems.map((item) => {
                    const meta = addedLine(item, myUserId);

                    if (item.kind === 'settlement') {
                      const amt = parseFloat(item.amount) || 0;
                      const iPaid = item.payer && item.payer.id === myUserId;
                      const iReceived = item.payee && item.payee.id === myUserId;
                      const label = iReceived ? 'you received' : iPaid ? 'you paid' : 'settle-up';
                      const color = iReceived ? 'var(--color-positive)' : iPaid ? '#ffffff' : 'var(--text-dim)';
                      return (
                        <div
                          key={`settlement-${item.id}`}
                          className="card"
                          onClick={() => setSelectedSettlement(item)}
                          style={{
                            padding: '0.85rem 1rem', display: 'flex', alignItems: 'center',
                            justifyContent: 'space-between', gap: '0.75rem', cursor: 'pointer',
                            borderLeft: isNew(item) ? '3px solid var(--accent-primary)' : undefined
                          }}
                        >
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#ffffff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              💸 {memberName(item.payer)} paid {memberName(item.payee)}
                              {isNew(item) && <NewBadge />}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.1rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {meta || 'Settle-up payment'}
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexShrink: 0 }}>
                            <div style={{ textAlign: 'right' }}>
                              <div style={{ fontSize: '0.7rem', color }}>{label}</div>
                              <div style={{ fontSize: '1.05rem', fontWeight: 800, color }}>{currency}{shortAmount(amt)}</div>
                            </div>
                            <ChevronRight size={16} color="var(--text-dim)" />
                          </div>
                        </div>
                      );
                    }

                    const exp = item;
                    const totalAmt = parseFloat(exp.amount) || 0;
                    const mine = myPosition(exp, myUserId);
                    let label, color, value;
                    if (!mine.involved) {
                      label = 'not involved'; color = 'var(--text-dim)'; value = null;
                    } else if (mine.net > 0.005) {
                      label = 'you lent'; color = 'var(--color-positive)'; value = mine.net;
                    } else if (mine.net < -0.005) {
                      label = 'you borrowed'; color = 'var(--color-negative)'; value = mine.net;
                    } else {
                      label = 'no balance'; color = 'var(--text-dim)'; value = null;
                    }

                    return (
                      <div
                        key={`expense-${exp.id}`}
                        className="card"
                        onClick={() => handleOpenExpenseModal(exp)}
                        style={{
                          padding: '0.85rem 1rem', display: 'flex', alignItems: 'center',
                          justifyContent: 'space-between', gap: '0.75rem', cursor: 'pointer',
                          borderLeft: (isNew(exp) || isUpdated(exp)) ? '3px solid var(--accent-primary)' : undefined
                        }}
                      >
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#ffffff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {getCleanTitle(exp.description)}
                            {isNew(exp) && <NewBadge />}
                            {isUpdated(exp) && <NewBadge label="Updated" />}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.1rem' }}>
                            <strong style={{ color: '#ffffff' }}>{payerSummary(exp, myUserId, members)}</strong> paid {currency}{shortAmount(totalAmt)}
                          </div>
                          {meta && (
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '0.1rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {meta}
                            </div>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexShrink: 0 }}>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '0.7rem', color }}>{label}</div>
                            {value !== null && (
                              <div style={{ fontSize: '1.05rem', fontWeight: 800, color }}>
                                {currency}{shortAmount(value)}
                              </div>
                            )}
                          </div>
                          <ChevronRight size={16} color="var(--text-dim)" />
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
                const isMe = m.id === myUserId;
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
            {payInfo && (
              <div style={{
                marginBottom: '0.75rem', padding: '0.55rem 0.75rem', fontSize: '0.8rem',
                backgroundColor: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)', color: 'var(--text-muted)',
                display: 'flex', justifyContent: 'space-between', gap: '0.5rem'
              }}>
                <span>{payInfo.text}</span>
                <button onClick={() => setPayInfo(null)} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}>
                  <X size={14} />
                </button>
              </div>
            )}
            {filteredDebts.length === 0 ? (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', textAlign: 'center', padding: '1rem 0' }}>
                Everyone in this group is completely settled up!
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {filteredDebts.map((d, idx) => {
                  const fromUser = members.find(m => m.id === d.from_user_id) || { name: `User #${d.from_user_id}` };
                  const toUser = members.find(m => m.id === d.to_user_id) || { name: `User #${d.to_user_id}` };

                  const fromIsMe = fromUser.id === myUserId;
                  const toIsMe = toUser.id === myUserId;

                  if (fromIsMe && toIsMe) return null;

                  const fromName = fromIsMe ? 'You' : fromUser.name.split(' ')[0];
                  const toName = toIsMe ? 'You' : toUser.name.split(' ')[0];
                  const rowKey = `${d.from_user_id}-${d.to_user_id}`;

                  return (
                    <React.Fragment key={idx}>
                    <div
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
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#ffffff', minWidth: 0 }}>
                        <strong>{fromName}</strong> {fromIsMe ? 'owe' : 'owes'} <strong>{toName}</strong>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                        <span style={{ fontWeight: 800, color: 'var(--accent-primary)' }}>
                          {currency}{Math.round(d.amount)}
                        </span>
                        {fromIsMe && toUser.has_upi && (
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handlePay(toUser, d.amount)}
                            style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                          >
                            Pay
                          </button>
                        )}
                        {toIsMe && (
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleNudge(fromUser, d.amount, rowKey)}
                            style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                            title={`Send ${fromUser.name.split(' ')[0]} a notification`}
                          >
                            Remind
                          </button>
                        )}
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => onOpenSettleUp(groupData, d.from_user_id, d.to_user_id, Number(d.amount).toFixed(2))}
                          style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                        >
                          Settle
                        </button>
                      </div>
                    </div>
                    {nudgeState[rowKey] && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', padding: '0 0.75rem' }}>
                        {nudgeState[rowKey]}
                      </div>
                    )}
                    </React.Fragment>
                  );
                })}

                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => onOpenSettleUp(groupData)}
                  style={{ marginTop: '0.5rem', width: '100%' }}
                >
                  <HandCoins size={14} />
                  <span>Record a different amount</span>
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
                      {payersOf(selectedExpenseDetails).length > 0
                        ? payersOf(selectedExpenseDetails).map(pay => {
                            const pUser = pay.user || members.find(m => m.id === pay.user_id);
                            const name = pUser ? pUser.name : 'Group Member';
                            return payersOf(selectedExpenseDetails).length > 1 ? `${name} (${currency}${shortAmount(parseFloat(pay.amount_paid))})` : name;
                          }).join(', ')
                        : (selectedExpenseDetails.created_by ? selectedExpenseDetails.created_by.name : 'Group Member')}
                    </strong>
                    {addedLine({ ...selectedExpenseDetails, kind: 'expense' }, myUserId) && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.25rem' }}>
                        {addedLine({ ...selectedExpenseDetails, kind: 'expense' }, myUserId)}
                      </div>
                    )}
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
                <span>Delete</span>
              </button>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {isGrocerySplit(selectedExpenseDetails) ? (
                  onOpenBlinkit && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => { setSelectedExpenseDetails(null); onOpenBlinkit(); }}
                      title="Grocery orders are changed with Re-Split in Quick Grocery Apps"
                    >
                      Re-split order
                    </button>
                  )
                ) : (
                  onEditExpense && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => { const exp = selectedExpenseDetails; setSelectedExpenseDetails(null); onEditExpense(exp, groupData); }}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                    >
                      <Pencil size={14} />
                      <span>Edit</span>
                    </button>
                  )
                )}

                <button className="btn btn-secondary btn-sm" onClick={() => setSelectedExpenseDetails(null)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SETTLE-UP PAYMENT DETAILS MODAL */}
      {selectedSettlement && (
        <div className="modal-overlay" onClick={() => setSelectedSettlement(null)}>
          <div className="modal-content" style={{ maxWidth: '420px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#ffffff' }}>Settle-up Payment</h3>
              <button onClick={() => setSelectedSettlement(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body" style={{ padding: '1rem' }}>
              <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#ffffff' }}>
                💸 {memberName(selectedSettlement.payer)} paid {memberName(selectedSettlement.payee)}
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--accent-primary)', margin: '0.35rem 0 0.75rem' }}>
                {currency}{(parseFloat(selectedSettlement.amount) || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                <span>Date: <span style={{ color: '#ffffff' }}>{formatDateGroupKey(selectedSettlement)}</span></span>
                {selectedSettlement.notes && <span>Note: <span style={{ color: '#ffffff' }}>{selectedSettlement.notes}</span></span>}
                {addedLine(selectedSettlement, myUserId) && <span>{addedLine(selectedSettlement, myUserId)}</span>}
              </div>
            </div>
            <div className="modal-footer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleDeleteSettlement(selectedSettlement.id)}
                style={{ color: 'var(--color-negative)', border: '1px solid rgba(239, 68, 68, 0.3)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
              >
                <Trash2 size={14} />
                <span>Delete</span>
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedSettlement(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
