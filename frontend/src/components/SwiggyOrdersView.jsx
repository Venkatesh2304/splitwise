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
  const [needsReconnect, setNeedsReconnect] = useState(false);

  // Selected order for splitting
  const [selectedOrderForSplit, setSelectedOrderForSplit] = useState(null);
  const [actionLoadingId, setActionLoadingId] = useState(null);

  const [manualJson, setManualJson] = useState('');
  const [syncingJson, setSyncingJson] = useState(false);
  const [authStarting, setAuthStarting] = useState(false);
  const [awaitingPaste, setAwaitingPaste] = useState(false);
  const [justConnected, setJustConnected] = useState(false);
  const [connectError, setConnectError] = useState(null);

  const fetchStatusAndOrders = async (forceRefresh = false) => {
    try {
      setLoading(true);
      setError(null);

      const activeUserId = currentUser?.id || '';

      const statusRes = await fetch(`${API_BASE_URL}/swiggy/status/?user_id=${encodeURIComponent(activeUserId)}`);
      const statusData = await statusRes.json();
      setStatusInfo(statusData);
      setNeedsReconnect(Boolean(statusData.needs_reconnect));

      if (statusData.is_logged_in) {
        const url = forceRefresh 
          ? `${API_BASE_URL}/swiggy/orders/?refresh=true&user_id=${encodeURIComponent(activeUserId)}`
          : `${API_BASE_URL}/swiggy/orders/?user_id=${encodeURIComponent(activeUserId)}`;

        const ordersRes = await fetch(url);
        const ordersData = await ordersRes.json();
        if (ordersRes.ok) {
          // The backend already returns Instamart and food merged and date-sorted.
          setOrders(ordersData.orders || []);
          setIsCached(Boolean(ordersData.cached));
          setNeedsReconnect(Boolean(ordersData.needs_reconnect));
        } else {
          setError(ordersData.error || 'Failed to fetch Swiggy orders.');
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
  }, [currentUser?.id]);

  // Swiggy's callback sends the browser back here with one of these set. Read it once,
  // then take it out of the URL so a reload doesn't replay it.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connected = params.get('swiggy_connected');
    const failed = params.get('swiggy_error');
    if (!connected && !failed) return;

    if (connected) {
      setJustConnected(true);
      fetchStatusAndOrders(true);
    } else {
      setConnectError(failed);
    }

    params.delete('swiggy_connected');
    params.delete('swiggy_error');
    const qs = params.toString();
    window.history.replaceState({}, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
  }, []);

  // One path for both Connect and Reconnect. The auth URL is minted at click time on
  // purpose: each /auth_url/ call replaces the stored PKCE verifier, so a URL captured
  // when the page loaded can carry a verifier that no longer matches.
  const startSwiggyLogin = async () => {
    try {
      setAuthStarting(true);
      setConnectError(null);
      const activeUserId = currentUser?.id || '';
      const res = await fetch(
        `${API_BASE_URL}/swiggy/auth_url/?user_id=${encodeURIComponent(activeUserId)}`,
        { cache: 'no-store' }
      );
      const data = await res.json();
      if (!res.ok || !data.auth_url) throw new Error(data.error || 'Could not start the Swiggy login.');

      if (data.public_callback) {
        // Swiggy can return to us directly: same tab, and the redirect lands back here.
        window.location.assign(data.auth_url);
        return;
      }
      // Swiggy has not whitelisted our callback, so sign-in ends on a page that won't
      // load and the URL has to come back by hand. New tab, so this one stays open to
      // paste into.
      window.open(data.auth_url, '_blank', 'noopener');
      setAwaitingPaste(true);
      setAuthStarting(false);
    } catch (err) {
      setConnectError(err.message || 'Could not start the Swiggy login.');
      setAuthStarting(false);
    }
  };

  const handleRemoveSplit = async (orderId, orderType) => {
    if (!window.confirm(`Remove split for order #${orderId} from Groceries group?`)) return;
    try {
      setActionLoadingId(orderId);
      const res = await fetch(`${API_BASE_URL}/swiggy/remove_split/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: String(orderId), actor_id: currentUser?.id, platform: orderType || 'INSTAMART' })
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

      if (decodedInput.includes("swiggy/callback") || decodedInput.startsWith("http://localhost")) {
        // Handle OOB URL copy-paste
        const queryStr = decodedInput.includes('?') ? decodedInput.split('?')[1] : decodedInput;
        const urlParams = new URLSearchParams(queryStr);
        const code = urlParams.get("code");
        const phone = urlParams.get("phone") || activeUserId;
        // Forward state too, so the nonce path validates for a URL pasted from a
        // current-style login.
        const state = urlParams.get("state") || '';

        if (!code) throw new Error("No authorization code found in the pasted URL");

        const res = await fetch(`${API_BASE_URL}/swiggy/callback/?code=${encodeURIComponent(code)}&phone=${encodeURIComponent(phone)}&state=${encodeURIComponent(state)}&ajax=1`, { method: 'GET' });
        if (res.ok) {
          setManualJson('');
          setAwaitingPaste(false);
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

  // Sign-in should come back on its own now. This stays as the escape hatch, and is
  // rendered both when signed out and when the session has expired — it used to be
  // reachable only when signed out, which is not the state you get stuck in.
  const manualFallback = (
    <details open={awaitingPaste} style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1.5rem', textAlign: 'left' }}>
      <summary style={{ fontSize: '0.75rem', color: awaitingPaste ? '#fc8019' : 'var(--text-dim)', cursor: 'pointer', fontWeight: awaitingPaste ? 700 : 400 }}>
        {awaitingPaste ? 'Step 2: paste the URL Swiggy sent you to' : 'Finish a sign-in that landed on a blank page'}
      </summary>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', margin: '0.75rem 0', lineHeight: '1.4' }}>
        Swiggy hasn't whitelisted this app's address yet, so after you sign in it sends you
        to a page that won't load. That's expected — copy the{' '}
        <strong>entire URL from that tab's address bar</strong> and paste it here to finish.
        (Raw JSON orders work here too.)
      </p>
      <textarea
        value={manualJson}
        onChange={(e) => setManualJson(e.target.value)}
        placeholder="Paste the callback URL from the address bar, OR raw JSON"
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
        {syncingJson ? 'Syncing...' : 'Finish sign-in / Sync orders'}
      </button>
    </details>
  );


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
              {isLoggedIn ? `Swiggy (${statusInfo.user_id || 'Connected'})` : 'Connect Swiggy'}
            </span>
            {isLoggedIn && (
              <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                {needsReconnect ? '⚠️ Session expired — showing saved orders' : (isCached ? '⚡ Cached (Instant)' : '🌐 Live Sync')}
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

      {justConnected && (
        <div className="card" style={{ padding: '0.9rem 1rem', marginBottom: '1rem', border: '1px solid rgba(16, 185, 129, 0.45)', backgroundColor: 'rgba(16, 185, 129, 0.06)' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--color-positive, #10b981)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <CheckCircle2 size={15} />
            <span>Swiggy connected — syncing your orders</span>
          </div>
        </div>
      )}

      {connectError && (
        <div className="card" style={{ padding: '0.9rem 1rem', marginBottom: '1rem', border: '1px solid var(--color-negative)', backgroundColor: 'rgba(239, 68, 68, 0.08)' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--color-negative)', marginBottom: '0.2rem' }}>
            Swiggy login didn't complete
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', margin: 0 }}>
            {connectError === 'exchange_failed' && 'Swiggy refused to complete the sign-in. Try again, and if it keeps failing the redirect URL may need allowlisting.'}
            {connectError === 'bad_state' && 'That sign-in had already been used or expired. Start a fresh one.'}
            {connectError === 'no_code' && 'Swiggy sent us back without an authorization code. Try again.'}
            {!['exchange_failed', 'bad_state', 'no_code'].includes(connectError) && connectError}
          </p>
        </div>
      )}

      {/* OAuth Login Link Banner */}
      {!isLoggedIn && (
        <div className="card" style={{ marginBottom: '1rem', padding: '1.25rem', textAlign: 'center' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: '1.4' }}>
            Authenticate via Swiggy's official MCP OAuth 2.0 portal to sync your live Instamart order history.
          </p>
          <button
            onClick={startSwiggyLogin}
            disabled={authStarting}
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
              border: 'none',
              cursor: authStarting ? 'default' : 'pointer',
              marginBottom: '1.5rem'
            }}
          >
            <span>{authStarting ? 'Opening Swiggy…' : 'Connect Swiggy MCP OAuth'}</span>
            <ExternalLink size={14} />
          </button>

          {manualFallback}
        </div>
      )}

      {needsReconnect && (
        <div className="card" style={{ padding: '0.9rem 1rem', marginBottom: '1rem', border: '1px solid rgba(245, 158, 11, 0.45)', backgroundColor: 'rgba(245, 158, 11, 0.06)' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f59e0b', marginBottom: '0.25rem' }}>
            Swiggy session expired
          </div>
          <p style={{ fontSize: '0.775rem', color: 'var(--text-dim)', margin: '0 0 0.6rem' }}>
            Swiggy sessions last about 5 days. The orders below are the ones already saved —
            reconnect to pull anything new.
          </p>
          <button
            onClick={startSwiggyLogin}
            disabled={authStarting}
            className="btn btn-sm"
            style={{ backgroundColor: '#fc8019', color: '#ffffff', display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.9rem', border: 'none', cursor: authStarting ? 'default' : 'pointer' }}
          >
            {authStarting ? 'Opening Swiggy…' : 'Reconnect Swiggy'}
          </button>
          {manualFallback}
        </div>
      )}

      {/* Loading state */}
      {loading && orders.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
          <p style={{ fontSize: '0.85rem' }}>Loading Swiggy orders...</p>
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
          <p style={{ fontSize: '0.85rem' }}>No recent Swiggy orders found.</p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {orders.map((order) => {
          const isSplit = Boolean(order.is_split);
          const isFood = String(order.order_type || '').toUpperCase() === 'SWIGGY_FOOD';
          const restaurantName = order.restaurant_name || order.full_order_json?.restaurant_name || '';
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
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                    <span style={{
                      fontSize: '0.6rem',
                      fontWeight: 700,
                      letterSpacing: '0.03em',
                      padding: '0.1rem 0.35rem',
                      borderRadius: 'var(--radius-sm)',
                      color: isFood ? '#f59e0b' : '#10b981',
                      backgroundColor: isFood ? 'rgba(245, 158, 11, 0.12)' : 'rgba(16, 185, 129, 0.12)'
                    }}>
                      {isFood ? 'FOOD' : 'INSTAMART'}
                    </span>
                    <span>{isFood && restaurantName ? restaurantName : `Order #${order.order_id}`}</span>
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
                      onClick={() => handleRemoveSplit(order.order_id, order.order_type)}
                      disabled={actionLoadingId === order.order_id}
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.725rem' }}
                      title="Remove from group"
                    >
                      Remove
                    </button>
                  )}

                  <button
                    className={`btn btn-sm ${isSplit ? 'btn-secondary' : 'btn-primary'}`}
                    onClick={() => setSelectedOrderForSplit({ ...order, order_type: order.order_type || 'INSTAMART' })}
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
