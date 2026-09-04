import React, { useState, useEffect } from 'react';
import ItemizedSplitModal from './ItemizedSplitModal';
import { API_BASE_URL } from '../services/api';
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

  const [manualJson, setManualJson] = useState('');
  const [syncingJson, setSyncingJson] = useState(false);

  const fetchStatusAndOrders = async (forceRefresh = false) => {
    try {
      setLoading(true);
      setError(null);

      const activeUserId = currentUser?.id || '';
      
      // Fetch Auth URL & status
      const authRes = await fetch(`${API_BASE_URL}/swiggy/auth_url/?user_id=${encodeURIComponent(activeUserId)}`);
      const authData = await authRes.json();
      setAuthUrl(authData.auth_url || '');

      const statusRes = await fetch(`${API_BASE_URL}/swiggy/status/?user_id=${encodeURIComponent(activeUserId)}`);
      const statusData = await statusRes.json();
      setStatusInfo(statusData);

      if (statusData.is_logged_in) {
        const url = forceRefresh 
          ? `${API_BASE_URL}/swiggy/orders/?refresh=true&user_id=${encodeURIComponent(activeUserId)}`
          : `${API_BASE_URL}/swiggy/orders/?user_id=${encodeURIComponent(activeUserId)}`;

        const ordersRes = await fetch(url);
        const ordersData = await ordersRes.json();
        if (ordersRes.ok) {
          const rawOrders = ordersData.orders || [];
          const sorted = [...rawOrders].sort((a, b) => {
            const parseDate = (d) => {
              if (!d || d === 'Recently') return 0;
              const p = Date.parse(d);
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
      const res = await fetch(`${API_BASE_URL}/swiggy/remove_split/`, {
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
      const activeUserId = currentUser?.id || '';
      await fetch(`${API_BASE_URL}/swiggy/logout/`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: activeUserId })
      });
      setOrders([]);
      fetchStatusAndOrders(true);
    } catch (e) {
      console.error(e);
    }
  };

  const handleManualSync = async () => {
    const input = manualJson.trim();
    if (!input) return;
    
    try {
      setSyncingJson(true);
      const activeUserId = currentUser?.id || '';

      let decodedInput = input;
      try {
        decodedInput = decodeURIComponent(input);
      } catch (e) {
        // Ignore if not fully encoded
      }

      if (decodedInput.startsWith("http://localhost") || decodedInput.includes("swiggy/callback")) {
        // Handle OOB URL copy-paste
        const queryStr = decodedInput.includes('?') ? decodedInput.split('?')[1] : decodedInput;
        const urlParams = new URLSearchParams(queryStr);
        const code = urlParams.get("code");
        const phone = urlParams.get("phone") || activeUserId;
        
        if (!code) throw new Error("No authorization code found in the pasted URL");
        
        const res = await fetch(`${API_BASE_URL}/swiggy/callback/?code=${encodeURIComponent(code)}&phone=${encodeURIComponent(phone)}&ajax=1`, { method: 'GET' });
        if (res.ok) {
          setManualJson('');
          fetchStatusAndOrders(true);
        } else {
          alert('Failed to complete Swiggy OAuth callback');
        }
      } else {
        // Handle direct JSON payload
        const res = await fetch(`${API_BASE_URL}/swiggy/sync_manual/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: activeUserId, json_data: input })
        });
        if (res.ok) {
          setManualJson('');
          fetchStatusAndOrders(true);
        } else {
          const data = await res.json();
          alert(data.error || 'Failed to sync manual JSON');
        }
      }
    } catch (err) {
      alert(err.message || 'Error syncing input');
    } finally {
      setSyncingJson(false);
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

    return { date: datePart, time: timePart };
  };

  const isLoggedIn = statusInfo && statusInfo.is_logged_in;
  const defaultAuthUrl = `https://mcp.swiggy.com/auth/authorize?response_type=code&client_id=swiggy-mcp&redirect_uri=${encodeURIComponent(`${API_BASE_URL}/swiggy/callback/`)}&code_challenge=anMh43oX8zlz5C87l0r9J9XOVaNaKWqDwB0TjTj7fdo&code_challenge_method=S256&state=splitwise_state_123&scope=mcp:tools`;

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
              {isLoggedIn ? `Swiggy Instamart (${statusInfo.user_id || 'Connected'})` : 'Connect Swiggy Instamart'}
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
            title="Refresh Swiggy Orders"
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>

          {isLoggedIn && (
            <button
              onClick={handleLogout}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-dim)',
                cursor: 'pointer',
                fontSize: '0.75rem',
                padding: '0.25rem 0.4rem'
              }}
            >
              Logout
            </button>
          )}
        </div>
      </div>

      {/* OAuth Login Link Banner */}
      {!isLoggedIn && (
        <div className="card" style={{ marginBottom: '1rem', padding: '1.25rem', textAlign: 'center' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.4' }}>
            Authenticate via Swiggy's official MCP OAuth 2.0 portal to sync your live Instamart order history.
          </p>
          <a
            href={authUrl || defaultAuthUrl}
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
              textDecoration: 'none',
              marginBottom: '1.5rem'
            }}
          >
            <span>Connect Swiggy MCP OAuth</span>
            <ExternalLink size={14} />
          </a>

          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1.5rem' }}>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: '0.75rem', lineHeight: '1.4' }}>
              <strong>Localhost Workaround:</strong> If the OAuth flow redirects to a broken <code>http://localhost...</code> page, copy the <strong>entire URL from your browser's address bar</strong> and paste it below. (Or paste raw JSON orders).
            </p>
            <textarea
              value={manualJson}
              onChange={(e) => setManualJson(e.target.value)}
              placeholder="Paste http://localhost:8000/api/swiggy/callback/?phone=... OR raw JSON"
              style={{
                width: '100%',
                minHeight: '100px',
                padding: '0.5rem',
                fontSize: '0.75rem',
                fontFamily: 'monospace',
                backgroundColor: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                marginBottom: '0.75rem',
                resize: 'vertical'
              }}
            />
            <button
              className="btn btn-sm"
              onClick={handleManualSync}
              disabled={syncingJson || !manualJson.trim()}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {syncingJson ? 'Syncing...' : 'Sync Orders via JSON'}
            </button>
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && orders.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '0.85rem' }}>Loading Swiggy Instamart orders...</p>
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

      {/* Swiggy Orders List */}
      {!loading && orders.length === 0 && isLoggedIn && (
        <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '0.85rem' }}>No recent Swiggy Instamart orders found.</p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {orders.map((order) => {
          const isSplit = Boolean(order.is_split);
          const total = parseFloat(order.total_amount) || 0;
          const { date, time } = formatDateTime(order.placed_at);
          const items = order.item_details || [];
          const productNames = items.map(i => i.name);

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
                    Swiggy Order #{order.order_id}
                  </div>
                  <div style={{ fontSize: '0.725rem', color: 'var(--text-dim)', marginTop: '0.1rem' }}>
                    {date} {time && `• ${time}`}
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
                      Remove
                    </button>
                  )}

                  <button
                    className={`btn btn-sm ${isSplit ? 'btn-secondary' : 'btn-primary'}`}
                    onClick={() => setSelectedOrderForSplit({ ...order, order_type: 'SWIGGY' })}
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
