import React, { useState, useEffect } from 'react';
import ItemizedSplitModal from './ItemizedSplitModal';
import { API_BASE_URL } from '../services/api';
import { ShoppingBag, Zap, CheckCircle2, RefreshCw, Trash2 } from 'lucide-react';

export default function BlinkitOrdersView({ groceriesGroup, currentUser, onExpenseAdded }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isCached, setIsCached] = useState(false);

  // Selected order for splitting
  const [selectedOrderForSplit, setSelectedOrderForSplit] = useState(null);
  const [actionLoadingId, setActionLoadingId] = useState(null);

  const fetchStatusAndOrders = async (forceRefresh = false) => {
    try {
      setLoading(true);
      setError(null);

      const activePhone = currentUser?.phone_number || '6382247549';
      const activeUserId = currentUser?.id || '';

      const url = forceRefresh 
        ? `${API_BASE_URL}/blinkit/orders/?refresh=true&user_id=${encodeURIComponent(activeUserId)}&phone=${encodeURIComponent(activePhone)}`
        : `${API_BASE_URL}/blinkit/orders/?user_id=${encodeURIComponent(activeUserId)}&phone=${encodeURIComponent(activePhone)}`;

      const ordersRes = await fetch(url);
      const ordersData = await ordersRes.json();
      
      if (ordersRes.ok) {
        const rawOrders = ordersData.orders || [];
        const sorted = [...rawOrders].sort((a, b) => {
          const parseDate = (d) => {
            if (!d || d === 'Recently') return 0;
            let str = String(d).trim();
            const now = new Date();
            if (str.toLowerCase().startsWith('today')) {
              const todayStr = `${now.getDate()} ${now.toLocaleString('default', { month: 'short' })} ${now.getFullYear()}`;
              str = str.replace(/today/i, todayStr);
            } else if (str.toLowerCase().startsWith('yesterday')) {
              const yest = new Date(now.getTime() - 86400000);
              const yestStr = `${yest.getDate()} ${yest.toLocaleString('default', { month: 'short' })} ${yest.getFullYear()}`;
              str = str.replace(/yesterday/i, yestStr);
            } else if (!/\d{4}/.test(str)) {
              str = `${str} ${now.getFullYear()}`;
            }
            const p = Date.parse(str);
            return isNaN(p) ? 0 : p;
          };
          const timeA = parseDate(a.placed_at);
          const timeB = parseDate(b.placed_at);
          if (timeA !== timeB) return timeB - timeA;
          return String(b.order_id || '').localeCompare(String(a.order_id || ''), undefined, { numeric: true });
        });
        setOrders(sorted);
        setIsCached(Boolean(ordersData.cached));
      } else {
        setError(ordersData.error || 'Failed to fetch Blinkit orders.');
        if (ordersData.orders) setOrders(ordersData.orders);
      }
    } catch (err) {
      console.error(err);
      setError('Connection error.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatusAndOrders(false);
  }, [currentUser]);

  const handleRemoveSplit = async (orderId) => {
    if (!window.confirm(`Remove split for order #${orderId} from Groceries group?`)) return;
    try {
      setActionLoadingId(orderId);
      const res = await fetch(`${API_BASE_URL}/blinkit/remove_split/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: String(orderId) })
      });

      if (res.ok) {
        await fetchStatusAndOrders(false);
        if (onExpenseAdded) onExpenseAdded();
      } else {
        alert('Failed to remove split.');
      }
    } catch (err) {
      alert('Error removing split.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const formatDateTime = (placedAt) => {
    if (!placedAt) return '';
    return placedAt;
  };

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      {/* Account Status & Extension Banner */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '1rem',
        padding: '0.65rem 0.85rem',
        backgroundColor: 'rgba(30, 41, 59, 0.6)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-color)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ShoppingBag size={18} color="#f59e0b" />
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ffffff', display: 'block', lineHeight: 1.2 }}>
              Blinkit Orders ({currentUser?.name || 'Synced'})
            </span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
              ⚡ Synced via Chrome Extension
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            onClick={() => fetchStatusAndOrders(true)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent-primary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '0.25rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(16, 185, 129, 0.1)'
            }}
            title="Refresh Blinkit Orders"
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Loading state */}
      {loading && orders.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '0.85rem' }}>Loading Blinkit orders...</p>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div style={{
          padding: '0.65rem 0.85rem',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid var(--color-negative)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-negative)',
          fontSize: '0.8rem',
          marginBottom: '1rem'
        }}>
          {error}
        </div>
      )}

      {/* Empty state */}
      {!loading && orders.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '0.85rem' }}>No Blinkit orders synced yet.</p>
          <p style={{ fontSize: '0.75rem', marginTop: '0.5rem', color: 'var(--text-dim)' }}>
            Use the <strong>Splitwise Blinkit Sync Chrome Extension</strong> on blinkit.com to sync your orders.
          </p>
        </div>
      )}

      {/* Blinkit Orders List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {orders.map((order) => {
          const isSplit = Boolean(order.is_split);
          const total = parseFloat(order.total_amount) || 0;
          const items = order.item_details || [];
          const productNames = order.product_names || items.map(i => i.name);

          return (
            <div
              key={order.order_id}
              className="card"
              style={{
                padding: '0.85rem 1rem',
                border: isSplit ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid var(--border-color)',
                backgroundColor: isSplit ? 'rgba(16, 185, 129, 0.03)' : 'rgba(30, 41, 59, 0.5)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ffffff' }}>
                    Blinkit Order #{order.order_id}
                  </div>
                  <div style={{ fontSize: '0.725rem', color: 'var(--text-dim)', marginTop: '0.1rem' }}>
                    {formatDateTime(order.placed_at)}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--accent-primary)' }}>
                    ₹{Math.round(total)}
                  </div>
                </div>
              </div>

              {/* Product list preview */}
              {productNames.length > 0 && (
                <div style={{
                  fontSize: '0.775rem',
                  color: 'var(--text-muted)',
                  marginBottom: '0.65rem',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  padding: '0.45rem 0.65rem',
                  borderRadius: 'var(--radius-sm)'
                }}>
                  {productNames.join(', ')}
                </div>
              )}

              {/* Split Status & Action Buttons */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                {isSplit ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--accent-primary)', fontSize: '0.75rem', fontWeight: 600 }}>
                    <CheckCircle2 size={14} />
                    <span>Split in Groceries Group</span>
                  </div>
                ) : (
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                    Not split yet
                  </span>
                )}

                <div style={{ display: 'flex', gap: '0.35rem' }}>
                  {isSplit && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleRemoveSplit(order.order_id)}
                      disabled={actionLoadingId === order.order_id}
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.725rem' }}
                      title="Remove from group"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}

                  <button
                    className={`btn btn-sm ${isSplit ? 'btn-secondary' : 'btn-primary'}`}
                    onClick={() => setSelectedOrderForSplit({ ...order, order_type: 'BLINKIT' })}
                    style={{ padding: '0.25rem 0.65rem', fontSize: '0.75rem' }}
                  >
                    <Zap size={13} />
                    <span>{isSplit ? 'Re-Split' : 'Split Order'}</span>
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Itemized Split Modal */}
      {selectedOrderForSplit && (
        <ItemizedSplitModal
          isOpen={Boolean(selectedOrderForSplit)}
          onClose={() => setSelectedOrderForSplit(null)}
          order={selectedOrderForSplit}
          groceriesGroup={groceriesGroup}
          currentUser={currentUser}
          onSplitSaved={() => {
            fetchStatusAndOrders(false);
            if (onExpenseAdded) onExpenseAdded();
          }}
        />
      )}
    </div>
  );
}
