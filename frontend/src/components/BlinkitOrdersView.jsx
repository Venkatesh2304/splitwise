import React, { useState, useEffect } from 'react';
import ItemizedSplitModal from './ItemizedSplitModal';
import { ShoppingBag, Zap, CheckCircle2, RefreshCw, Trash2 } from 'lucide-react';

export default function BlinkitOrdersView({ groceriesGroup, currentUser, onExpenseAdded }) {
  const [statusInfo, setStatusInfo] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isCached, setIsCached] = useState(false);

  // In-tab OTP state
  const [phone, setPhone] = useState('6382247549');
  const [otpCode, setOtpCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [authSubmitting, setAuthSubmitting] = useState(false);

  // Selected order for splitting
  const [selectedOrderForSplit, setSelectedOrderForSplit] = useState(null);
  const [actionLoadingId, setActionLoadingId] = useState(null);

  const fetchStatusAndOrders = async (forceRefresh = false) => {
    try {
      setLoading(true);
      setError(null);

      const statusRes = await fetch('http://localhost:8000/api/blinkit/status/');
      const statusData = await statusRes.json();
      setStatusInfo(statusData);

      if (statusData.phone_number) setPhone(statusData.phone_number);

      if (statusData.is_logged_in) {
        const url = forceRefresh 
          ? 'http://localhost:8000/api/blinkit/orders/?refresh=true'
          : 'http://localhost:8000/api/blinkit/orders/';

        const ordersRes = await fetch(url);
        const ordersData = await ordersRes.json();
        if (ordersRes.ok) {
          setOrders(ordersData.orders || []);
          setIsCached(Boolean(ordersData.cached));
        } else {
          setError(ordersData.error || 'Failed to fetch Blinkit orders.');
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

  const handleSendOtp = async (e) => {
    e.preventDefault();
    if (!phone.trim()) return;
    try {
      setAuthSubmitting(true);
      const res = await fetch('http://localhost:8000/api/blinkit/send_otp/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: phone.trim() })
      });
      const data = await res.json();
      if (res.ok && (data.success || data.ok)) {
        setOtpSent(true);
      } else {
        alert(data.error || 'Failed to send OTP.');
      }
    } catch (err) {
      alert(err.message);
    } finally {
      setAuthSubmitting(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    if (!otpCode.trim()) return;
    try {
      setAuthSubmitting(true);
      const res = await fetch('http://localhost:8000/api/blinkit/verify_otp/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: phone.trim(), otp: otpCode.trim() })
      });
      const data = await res.json();
      if (res.ok && (data.success || data.ok)) {
        setOtpSent(false);
        setOtpCode('');
        fetchStatusAndOrders(true);
      } else {
        alert(data.error || data.message || 'OTP verification failed.');
      }
    } catch (err) {
      alert(err.message);
    } finally {
      setAuthSubmitting(false);
    }
  };

  const handleRemoveSplit = async (orderId) => {
    if (!window.confirm(`Remove split for order #${orderId} from Groceries group?`)) return;
    try {
      setActionLoadingId(orderId);
      const res = await fetch('http://localhost:8000/api/blinkit/remove_split/', {
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
      await fetch('http://localhost:8000/api/blinkit/logout/', { method: 'POST' });
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
          <ShoppingBag size={18} color="#f59e0b" />
          <div>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#ffffff', display: 'block', lineHeight: 1.2 }}>
              {isLoggedIn ? `Blinkit (${statusInfo.phone_number || statusInfo.phone || '6382247549'})` : 'Connect Blinkit'}
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
            title="Fetch new orders from Blinkit"
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

      {/* Login OTP Form if not logged in */}
      {!isLoggedIn && (
        <div className="card" style={{ marginBottom: '1rem', padding: '1rem' }}>
          {!otpSent ? (
            <form onSubmit={handleSendOtp} style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Mobile number"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
              <button type="submit" className="btn btn-blinkit btn-sm" disabled={authSubmitting}>
                {authSubmitting ? 'Sending...' : 'Send OTP'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyOtp} style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type="text"
                className="form-input"
                placeholder="SMS OTP"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                autoFocus
              />
              <button type="submit" className="btn btn-blinkit btn-sm" disabled={authSubmitting}>
                {authSubmitting ? 'Verifying...' : 'Verify'}
              </button>
            </form>
          )}
        </div>
      )}

      {/* Orders List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Fetching Blinkit orders...
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
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent-primary)', marginBottom: '0.25rem' }}>
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
                        className={isAlreadySplit ? "btn btn-secondary btn-sm" : "btn btn-blinkit btn-sm"}
                        onClick={() => setSelectedOrderForSplit(ord)}
                        disabled={isActionBusy}
                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
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
