import React, { useState, useEffect } from 'react';
import ItemizedSplitModal from './ItemizedSplitModal';
import { ShoppingCart, Zap, CheckCircle2, RefreshCw, ExternalLink } from 'lucide-react';

export default function SwiggyOrdersView({ groceriesGroup, currentUser, onExpenseAdded }) {
  const [statusInfo, setStatusInfo] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isCached, setIsCached] = useState(false);
  const [authUrl, setAuthUrl] = useState('');

  // Selected order for splitting
  const [selectedOrderForSplit, setSelectedOrderForSplit] = useState(null);
  const [actionLoadingId, setActionLoadingId] = useState(null);

  const fetchStatusAndOrders = async (forceRefresh = false) => {
    try {
      setLoading(true);
      setError(null);

      // Fetch Auth URL & status
      const authRes = await fetch('http://localhost:8000/api/swiggy/auth_url/');
      const authData = await authRes.json();
      setAuthUrl(authData.auth_url || '');

      const statusRes = await fetch('http://localhost:8000/api/swiggy/status/');
      const statusData = await statusRes.json();
      setStatusInfo(statusData);

      if (statusData.is_logged_in) {
        const url = forceRefresh 
          ? 'http://localhost:8000/api/swiggy/orders/?refresh=true'
          : 'http://localhost:8000/api/swiggy/orders/';

        const ordersRes = await fetch(url);
        const ordersData = await ordersRes.json();
        if (ordersRes.ok) {
          setOrders(ordersData.orders || []);
          setIsCached(Boolean(ordersData.cached));
        } else {
          setError(ordersData.error || 'Failed to fetch Swiggy Instamart orders.');
        }
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
  }, []);

  const handleRemoveSplit = async (orderId) => {
    if (!window.confirm(`Remove split for order #${orderId} from Groceries group?`)) return;
    try {
      setActionLoadingId(orderId);
      const res = await fetch('http://localhost:8000/api/swiggy/remove_split/', {
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

  const handleLogout = async () => {
    try {
      await fetch('http://localhost:8000/api/swiggy/logout/', { method: 'POST' });
      setOrders([]);
      fetchStatusAndOrders(true);
    } catch (e) {
      console.error(e);
    }
  };

  const formatDateTime = (placedAt) => {
    if (!placedAt) return { date: 'Recently', time: '' };
    let datePart = placedAt;
    let timePart = '';

    if (placedAt.includes(', ')) {
      const parts = placedAt.split(', ');
      datePart = parts[0];
      timePart = parts[1] || '';
    }

    // Strip 4-digit year (e.g. 2026)
    datePart = datePart.replace(/\s*\d{4}\b/g, '').trim();

    return { date: datePart, time: timePart };
  };

  const isLoggedIn = statusInfo?.is_logged_in;

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      {/* Account Status & Cache Banner */}
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
          <ShoppingCart size={18} color="#fc8019" />
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ffffff', display: 'block', lineHeight: 1.2 }}>
              {isLoggedIn ? `Swiggy Instamart (${statusInfo.phone_number || '9965817968'})` : 'Connect Swiggy Instamart'}
            </span>
            {isLoggedIn && (
              <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                {isCached ? '⚡ Cached (Instant)' : '🌐 Live Sync'}
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            onClick={() => fetchStatusAndOrders(true)}
            style={{
              background: 'none',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              color: '#ffffff',
              cursor: 'pointer',
              padding: '0.25rem 0.5rem',
              fontSize: '0.75rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem'
            }}
            title="Fetch new orders from Swiggy Instamart"
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>

          {isLoggedIn ? (
            <button
              onClick={handleLogout}
              style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: '0.75rem' }}
            >
              Logout
            </button>
          ) : null}
        </div>
      </div>

      {/* Swiggy OAuth Connect Card if not logged in */}
      {!isLoggedIn && (
        <div className="card" style={{ marginBottom: '1rem', padding: '1.25rem', textAlign: 'center' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.4' }}>
            Authenticate via Swiggy's official MCP OAuth 2.0 portal to sync your live Instamart order history.
          </p>
          <a
            href={authUrl || "https://mcp.swiggy.com/auth/authorize?response_type=code&client_id=swiggy-mcp&redirect_uri=http://localhost:8000/api/swiggy/callback/&code_challenge=anMh43oX8zlz5C87l0r9J9XOVaNaKWqDwB0TjTj7fdo&code_challenge_method=S256&state=splitwise_state_123&scope=mcp:tools"}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-sm"
            style={{
              backgroundColor: '#fc8019',
              color: '#ffffff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.45rem 1rem',
              fontSize: '0.85rem',
              fontWeight: 600,
              textDecoration: 'none'
            }}
          >
            <ExternalLink size={15} />
            <span>Connect Swiggy MCP (OAuth)</span>
          </a>
        </div>
      )}

      {/* Orders List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Fetching Swiggy Instamart orders...
        </div>
      ) : orders.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '0.85rem' }}>No orders found.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {orders.map((ord, idx) => {
            const isAlreadySplit = Boolean(ord.is_split);
            const isActionBusy = actionLoadingId === ord.order_id;
            const { date: dateStr, time: timeStr } = formatDateTime(ord.placed_at);

            return (
              <div key={ord.order_id || idx} className="card" style={{ padding: '0.85rem 1rem' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.15rem' }}>
                      <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#ffffff' }}>
                        {dateStr}
                      </div>

                      {/* Split Status Badge */}
                      {isAlreadySplit ? (
                        <span className="balance-tag positive" style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem' }}>
                          <CheckCircle2 size={12} />
                          <span>Split in Group</span>
                        </span>
                      ) : (
                        <span className="balance-tag neutral" style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem' }}>
                          Not Split Yet
                        </span>
                      )}
                    </div>

                    {timeStr && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        {timeStr}
                      </div>
                    )}
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fc8019', marginBottom: '0.25rem' }}>
                      ₹{ord.total_amount ? Math.round(ord.total_amount) : 0}
                    </div>

                    <div style={{ display: 'flex', gap: '0.35rem', justifyContent: 'flex-end' }}>
                      {isAlreadySplit && (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleRemoveSplit(ord.order_id)}
                          disabled={isActionBusy}
                          style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem', color: 'var(--color-negative)' }}
                          title="Remove split from group"
                        >
                          <Trash2 size={12} />
                          <span>Remove</span>
                        </button>
                      )}

                      <button
                        className={isAlreadySplit ? "btn btn-secondary btn-sm" : "btn btn-sm"}
                        onClick={() => setSelectedOrderForSplit(ord)}
                        disabled={isActionBusy}
                        style={{
                          padding: '0.3rem 0.6rem',
                          fontSize: '0.75rem',
                          backgroundColor: isAlreadySplit ? undefined : '#fc8019',
                          color: '#ffffff',
                          border: 'none'
                        }}
                      >
                        <Zap size={12} />
                        <span>{isAlreadySplit ? 'Re-Split' : 'Split Order'}</span>
                      </button>
                    </div>
                  </div>
                </div>

                {/* Items list summary */}
                <div style={{ fontSize: '0.775rem', color: 'var(--text-muted)', lineHeight: '1.4', paddingTop: '0.4rem', borderTop: '1px solid var(--border-color)' }}>
                  {(ord.product_names || []).join(' • ')}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Split Modal */}
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
