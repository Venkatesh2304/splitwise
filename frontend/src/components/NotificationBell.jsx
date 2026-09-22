import React, { useEffect, useRef, useState } from 'react';
import { Bell, BellOff, BellRing } from 'lucide-react';
import { SECURE_APP_URL } from '../config';

const BLOCKED_HELP = 'Notifications are blocked for this site. Tap the icon left of the address bar (or Chrome ⋮ → Settings → Site settings → Notifications), allow them, then reload.';
const UNSUPPORTED_HELP = 'This browser can’t show notifications. On iPhone: open the app in Safari → Share → Add to Home Screen, then open it from the Home Screen.';

export default function NotificationBell({ state, onEnable, onDisable, onTest }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [position, setPosition] = useState({ top: 44, right: 12, width: 300 });
  const wrapRef = useRef(null);
  const buttonRef = useRef(null);

  // Hangs under the bell, but never past either edge of the screen: at phone width a
  // popover anchored to the button alone runs off the left, and the page clips it
  const toggle = () => {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const width = Math.min(300, window.innerWidth - 24);
      const right = Math.max(12, Math.min(window.innerWidth - rect.right, window.innerWidth - width - 12));
      setPosition({ top: rect.bottom + 8, right, width });
    }
    setOpen(!open);
    setMessage(null);
  };

  useEffect(() => {
    if (!open) return;
    const close = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  const run = async (action) => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await action();
      if (typeof result === 'string') setMessage({ ok: true, text: result });
    } catch (err) {
      setMessage({ ok: false, text: err.message || 'Something went wrong.' });
    } finally {
      setBusy(false);
    }
  };

  const Icon = state === 'on' ? BellRing : (state === 'off' ? Bell : BellOff);

  let body;
  if (state === 'on') {
    body = (
      <>
        <p>Notifications are <strong style={{ color: 'var(--accent-primary)' }}>on</strong> for this device. You'll hear when someone adds, edits or deletes an expense you're in, or settles up with you.</p>
        <div style={rowStyle}>
          <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => run(onTest)}>Send test</button>
          <button className="btn btn-secondary btn-sm" disabled={busy} onClick={() => run(onDisable)}>Turn off</button>
        </div>
      </>
    );
  } else if (state === 'off') {
    body = (
      <>
        <p>Get a notification when someone adds, edits or deletes an expense you're in, or settles up with you, even when the app is closed.</p>
        <div style={rowStyle}>
          <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => run(onEnable)}>
            {busy ? 'Turning on…' : 'Turn on notifications'}
          </button>
        </div>
      </>
    );
  } else if (state === 'denied') {
    body = <p>{BLOCKED_HELP}</p>;
  } else if (state === 'insecure') {
    body = (
      <>
        <p>Notifications only work on the app's secure (https) address.</p>
        {SECURE_APP_URL ? (
          <div style={rowStyle}>
            <a className="btn btn-primary btn-sm" href={SECURE_APP_URL} style={{ textDecoration: 'none' }}>Open secure app</a>
          </div>
        ) : (
          <p style={{ color: 'var(--text-dim)' }}>It isn't set up yet.</p>
        )}
      </>
    );
  } else if (state === 'unsupported') {
    body = <p>{UNSUPPORTED_HELP}</p>;
  } else {
    body = <p>Checking…</p>;
  }

  return (
    <span ref={wrapRef} style={{ position: 'relative', display: 'flex' }}>
      <button
        ref={buttonRef}
        onClick={toggle}
        title="Notifications"
        aria-label="Notifications"
        style={{
          background: 'none',
          border: 'none',
          color: state === 'on' ? 'var(--accent-primary)' : 'var(--text-muted)',
          cursor: 'pointer',
          padding: '0.25rem 0.4rem',
          display: 'flex',
          alignItems: 'center',
          position: 'relative'
        }}
      >
        <Icon size={18} />
        {state === 'off' && (
          <span style={{ position: 'absolute', top: 3, right: 4, width: 7, height: 7, borderRadius: '50%', backgroundColor: 'var(--accent-blinkit)' }} />
        )}
      </button>

      {open && (
        <div style={{
          position: 'fixed',
          top: position.top,
          right: position.right,
          width: position.width,
          // index.css sets `* { max-width: 100% }`, which would squeeze this to the
          // width of the bell button
          maxWidth: 'none',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow-md)',
          padding: '0.85rem',
          fontSize: '0.8rem',
          color: 'var(--text-main)',
          lineHeight: 1.45,
          zIndex: 60
        }}>
          <div style={{ fontWeight: 700, marginBottom: '0.4rem' }}>Notifications</div>
          {body}
          {message && (
            <p style={{ marginTop: '0.6rem', color: message.ok ? 'var(--accent-primary)' : 'var(--color-negative)' }}>
              {message.text}
            </p>
          )}
        </div>
      )}
    </span>
  );
}

const rowStyle = { display: 'flex', gap: '0.5rem', marginTop: '0.65rem', flexWrap: 'wrap' };
