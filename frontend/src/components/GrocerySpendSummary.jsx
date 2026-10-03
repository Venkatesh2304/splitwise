import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { ShoppingBag, Tag, Layers, Users, ChevronDown, ChevronUp, Receipt } from 'lucide-react';

const round = (n) => Math.round(Number(n) || 0).toLocaleString('en-IN');

export default function GrocerySpendSummary({ groupId, initialGroceryData, currency = '₹', activeMonth }) {
  const [filterUser, setFilterUser] = useState('all'); // 'all' or user_id
  const [viewMode, setViewMode] = useState('category'); // 'category' | 'product'
  const [timeScope, setTimeScope] = useState('month'); // 'month' | 'all'
  const [groceryData, setGroceryData] = useState(initialGroceryData || null);
  const [loading, setLoading] = useState(false);
  const [expandedItems, setExpandedItems] = useState({});

  // Sync initial data if month or initial data changes and user hasn't toggled away
  useEffect(() => {
    if (timeScope === 'month' && filterUser === 'all' && initialGroceryData) {
      setGroceryData(initialGroceryData);
    }
  }, [initialGroceryData, activeMonth]);

  // Fetch updated data when filterUser or timeScope changes
  useEffect(() => {
    let cancelled = false;
    const fetchGrocery = async () => {
      setLoading(true);
      try {
        const res = await api.getGroupGrocerySummary(groupId, {
          userId: filterUser === 'all' ? null : filterUser,
          month: timeScope === 'month' ? activeMonth : null,
        });
        if (!cancelled && res) {
          setGroceryData(res);
        }
      } catch (err) {
        console.error('Failed to load spend summary:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchGrocery();
    return () => { cancelled = true; };
  }, [groupId, filterUser, timeScope, activeMonth]);

  const toggleExpand = (key) => {
    setExpandedItems((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (!groceryData && loading) {
    return (
      <div className="card" style={{ padding: '1.25rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.825rem' }}>
        Loading spend breakdown…
      </div>
    );
  }

  const users = groceryData?.available_users || [];
  const rows = viewMode === 'category' ? (groceryData?.categories || []) : (groceryData?.products || []);
  const maxSpend = Math.max(...rows.map((r) => r.spend), 1);
  const totalSpend = groceryData?.total_spend || 0;
  const totalOrders = groceryData?.total_orders || 0;
  const itemizedSpend = groceryData?.itemized_spend ?? totalSpend;
  const nonItemizedSpend = groceryData?.non_itemized_spend ?? 0;
  const itemizedOrders = groceryData?.itemized_orders ?? totalOrders;
  const nonItemizedOrders = groceryData?.non_itemized_orders ?? 0;

  return (
    <div className="card" style={{ padding: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
      {/* Title & Badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <Receipt size={17} style={{ color: 'var(--accent-primary)' }} />
            <span style={{ fontSize: '0.95rem', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.01em' }}>
              Spendings
            </span>
          </div>
          <p style={{ fontSize: '0.725rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            {filterUser === 'all'
              ? 'Itemized and non-itemized group spends categorized by deterministic keywords'
              : `Exact splits assigned to ${groceryData?.active_user?.name || 'this user'}`}
          </p>
        </div>

        {/* Time Scope Toggle: Month vs All Time */}
        <div style={{ display: 'flex', backgroundColor: 'rgba(255, 255, 255, 0.05)', borderRadius: '999px', padding: '2px', border: '1px solid var(--border-color)' }}>
          <button
            type="button"
            onClick={() => setTimeScope('month')}
            style={{
              padding: '0.2rem 0.65rem',
              borderRadius: '999px',
              border: 'none',
              fontSize: '0.7rem',
              fontWeight: timeScope === 'month' ? 700 : 500,
              backgroundColor: timeScope === 'month' ? 'var(--accent-primary)' : 'transparent',
              color: timeScope === 'month' ? '#ffffff' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            This Month
          </button>
          <button
            type="button"
            onClick={() => setTimeScope('all')}
            style={{
              padding: '0.2rem 0.65rem',
              borderRadius: '999px',
              border: 'none',
              fontSize: '0.7rem',
              fontWeight: timeScope === 'all' ? 700 : 500,
              backgroundColor: timeScope === 'all' ? 'var(--accent-primary)' : 'transparent',
              color: timeScope === 'all' ? '#ffffff' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            All Time
          </button>
        </div>
      </div>

      {/* High-Level Spend Breakdown Numbers: Itemized vs Non-Itemized */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: '0.5rem',
      }}>
        <div style={{
          padding: '0.65rem 0.75rem',
          backgroundColor: 'rgba(255, 255, 255, 0.04)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-color)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.15rem'
        }}>
          <span style={{ fontSize: '0.675rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Total Spend
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 800, color: '#ffffff' }}>
            {currency}{round(totalSpend)}
          </span>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-dim)' }}>
            {totalOrders} {totalOrders === 1 ? 'expense' : 'expenses'}
          </span>
        </div>

        <div style={{
          padding: '0.65rem 0.75rem',
          backgroundColor: 'rgba(16, 185, 129, 0.08)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.15rem'
        }}>
          <span style={{ fontSize: '0.675rem', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
            Itemized Split
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--accent-primary)' }}>
            {currency}{round(itemizedSpend)}
          </span>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-dim)' }}>
            {itemizedOrders} {itemizedOrders === 1 ? 'order' : 'orders'}
          </span>
        </div>

        <div style={{
          padding: '0.65rem 0.75rem',
          backgroundColor: 'rgba(56, 189, 248, 0.08)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.15rem'
        }}>
          <span style={{ fontSize: '0.675rem', fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase' }}>
            Non-Itemized
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 800, color: '#38bdf8' }}>
            {currency}{round(nonItemizedSpend)}
          </span>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-dim)' }}>
            {nonItemizedOrders} {nonItemizedOrders === 1 ? 'expense' : 'expenses'}
          </span>
        </div>
      </div>

      {/* Member Filter Pills */}
      <div>
        <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <Users size={12} />
          <span>Filter by Roommate ({filterUser === 'all' ? 'Total Group Spend' : `Split on ${groceryData?.active_user?.name || 'Member'}`})</span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
          <button
            type="button"
            onClick={() => setFilterUser('all')}
            style={{
              padding: '0.25rem 0.65rem',
              borderRadius: '999px',
              border: filterUser === 'all' ? '1px solid var(--accent-primary)' : '1px solid var(--border-color)',
              fontSize: '0.725rem',
              fontWeight: filterUser === 'all' ? 700 : 500,
              backgroundColor: filterUser === 'all' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.03)',
              color: filterUser === 'all' ? 'var(--accent-primary)' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            Total Group
          </button>
          {users.map((u) => (
            <button
              key={u.id}
              type="button"
              onClick={() => setFilterUser(String(u.id))}
              style={{
                padding: '0.25rem 0.65rem',
                borderRadius: '999px',
                border: filterUser === String(u.id) ? '1px solid var(--accent-primary)' : '1px solid var(--border-color)',
                fontSize: '0.725rem',
                fontWeight: filterUser === String(u.id) ? 700 : 500,
                backgroundColor: filterUser === String(u.id) ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                color: filterUser === String(u.id) ? 'var(--accent-primary)' : 'var(--text-muted)',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              {u.name}
            </button>
          ))}
        </div>
      </div>

      {/* View Mode Switcher: By Category vs By Product Keyword */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: 'rgba(15, 23, 42, 0.6)',
        borderRadius: 'var(--radius-sm)',
        padding: '0.45rem 0.65rem',
        border: '1px solid var(--border-color)',
        gap: '0.5rem',
        flexWrap: 'wrap'
      }}>
        {/* Metric Summary */}
        <div style={{ fontSize: '0.75rem', color: '#ffffff', fontWeight: 600 }}>
          <span style={{ color: 'var(--accent-primary)', fontWeight: 800, fontSize: '0.9rem' }}>
            {currency}{round(totalSpend)}
          </span>
          <span style={{ color: 'var(--text-muted)', marginLeft: '0.4rem' }}>
            {filterUser === 'all' ? 'total spend' : `split on ${groceryData?.active_user?.name || 'user'}`} · {totalOrders} {totalOrders === 1 ? 'expense' : 'expenses'}
          </span>
        </div>

        {/* View Mode Toggle Buttons */}
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          <button
            type="button"
            onClick={() => setViewMode('category')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
              padding: '0.25rem 0.6rem',
              borderRadius: '6px',
              border: viewMode === 'category' ? '1px solid var(--accent-primary)' : '1px solid transparent',
              fontSize: '0.725rem',
              fontWeight: viewMode === 'category' ? 700 : 500,
              backgroundColor: viewMode === 'category' ? 'rgba(16, 185, 129, 0.2)' : 'transparent',
              color: viewMode === 'category' ? '#ffffff' : 'var(--text-muted)',
              cursor: 'pointer'
            }}
          >
            <Layers size={13} />
            <span>By Category</span>
          </button>
          <button
            type="button"
            onClick={() => setViewMode('product')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
              padding: '0.25rem 0.6rem',
              borderRadius: '6px',
              border: viewMode === 'product' ? '1px solid var(--accent-primary)' : '1px solid transparent',
              fontSize: '0.725rem',
              fontWeight: viewMode === 'product' ? 700 : 500,
              backgroundColor: viewMode === 'product' ? 'rgba(16, 185, 129, 0.2)' : 'transparent',
              color: viewMode === 'product' ? '#ffffff' : 'var(--text-muted)',
              cursor: 'pointer'
            }}
          >
            <Tag size={13} />
            <span>By Product</span>
          </button>
        </div>
      </div>

      {/* Rows List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
          Updating breakdown…
        </div>
      ) : rows.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-dim)', fontSize: '0.8rem' }}>
          No itemized items recorded for this selection.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {rows.map((row, idx) => {
            const rowKey = row.name || row.keyword;
            const isExpanded = !!expandedItems[rowKey];
            const barWidth = maxSpend > 0 ? Math.max(3, (row.spend / maxSpend) * 100) : 0;
            const topItems = row.top_items || [];

            return (
              <div
                key={rowKey}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.25rem',
                  padding: '0.25rem 0'
                }}
              >
                {/* Row Header */}
                <div
                  onClick={() => topItems.length > 0 && toggleExpand(rowKey)}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    cursor: topItems.length > 0 ? 'pointer' : 'default',
                    fontSize: '0.8rem'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', minWidth: 0 }}>
                    <span style={{ color: '#ffffff', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {rowKey}
                    </span>
                    {topItems.length > 0 && (
                      <span style={{ color: 'var(--text-dim)' }}>
                        {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0, marginLeft: '0.5rem' }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.725rem' }}>
                      {row.quantity} {row.quantity === 1 ? 'unit' : 'units'} · {row.percent}%
                    </span>
                    <span style={{ color: '#ffffff', fontWeight: 700 }}>
                      {currency}{round(row.spend)}
                    </span>
                  </div>
                </div>

                {/* Progress Bar */}
                <div style={{ height: '6px', backgroundColor: 'rgba(148, 163, 184, 0.12)', borderRadius: '999px', overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${barWidth}%`,
                      height: '100%',
                      backgroundColor: viewMode === 'category' ? 'var(--accent-primary)' : '#38bdf8',
                      borderRadius: '999px',
                      transition: 'width 0.3s ease'
                    }}
                  />
                </div>

                {/* Top Matched Items Subtext / Expansion */}
                {topItems.length > 0 && (
                  <div style={{
                    fontSize: '0.7rem',
                    color: 'var(--text-dim)',
                    paddingLeft: '0.2rem',
                    marginTop: '0.1rem',
                    display: isExpanded ? 'flex' : 'block',
                    flexDirection: 'column',
                    gap: '0.2rem',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: isExpanded ? 'normal' : 'nowrap'
                  }}>
                    {isExpanded ? (
                      <div style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: '0.35rem 0.5rem', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Top Purchases:</div>
                        {topItems.map((it, i) => (
                          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', margin: '0.15rem 0' }}>
                            <span style={{ color: 'var(--text-muted)' }}>• {it.name} (x{it.quantity})</span>
                            <span style={{ color: '#ffffff', fontWeight: 600 }}>{currency}{round(it.spend)}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span>
                        Includes: {topItems.map((it) => `${it.name} (x${it.quantity})`).join(', ')}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
