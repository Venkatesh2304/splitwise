import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const monthLabel = (month) => {
  if (!month) return '';
  const [year, mon] = month.split('-');
  return `${MONTHS[parseInt(mon, 10) - 1]} ${year}`;
};

const round = (n) => Math.round(Number(n) || 0).toLocaleString('en-IN');

// One bar per row, widths relative to the largest value rather than the total, so small
// categories stay visible
function Bars({ rows, currency, max }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
      {rows.map((row) => (
        <div key={row.key}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '0.2rem' }}>
            <span style={{ color: '#ffffff', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {row.label}
            </span>
            <span style={{ color: 'var(--text-muted)', flexShrink: 0, marginLeft: '0.5rem' }}>
              {currency}{round(row.value)}{row.note ? ` · ${row.note}` : ''}
            </span>
          </div>
          <div style={{ height: '6px', backgroundColor: 'rgba(148, 163, 184, 0.15)', borderRadius: '999px', overflow: 'hidden' }}>
            <div style={{
              width: `${max > 0 ? Math.max(2, (row.value / max) * 100) : 0}%`,
              height: '100%',
              backgroundColor: row.color || 'var(--accent-primary)',
              borderRadius: '999px'
            }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function GroupSummary({ groupId, currentUserId, refreshToken }) {
  const [month, setMonth] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setError(null);
        const result = await api.getGroupSummary(groupId, month, currentUserId);
        if (cancelled) return;
        setData(result);
        if (!month) setMonth(result.month);
      } catch (err) {
        if (!cancelled) setError('Could not load the summary.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [groupId, month, currentUserId, refreshToken]);

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading summary…</div>;
  }
  if (error || !data) {
    return <div className="card" style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--color-negative)', fontSize: '0.85rem' }}>{error}</div>;
  }

  const months = data.available_months || [];
  const index = months.indexOf(data.month);
  const older = index >= 0 && index < months.length - 1 ? months[index + 1] : null;
  const newer = index > 0 ? months[index - 1] : null;
  const currency = data.currency;

  const changeLabel = data.previous_total > 0
    ? `${data.change >= 0 ? '+' : '−'}${currency}${round(Math.abs(data.change))} vs ${monthLabel(data.previous_month)}`
    : `Nothing recorded in ${monthLabel(data.previous_month)}`;

  const maxPaid = Math.max(...data.people.map(p => Math.max(p.paid, p.share)), 0);
  const maxCategory = Math.max(...data.categories.map(c => c.total), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Month switcher */}
      <div className="card" style={{ padding: '0.65rem 0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => older && setMonth(older)}
          disabled={!older}
          style={{ padding: '0.25rem 0.5rem', opacity: older ? 1 : 0.35 }}
        >
          <ChevronLeft size={14} />
        </button>
        <span style={{ fontWeight: 700, color: '#ffffff' }}>{monthLabel(data.month)}</span>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => newer && setMonth(newer)}
          disabled={!newer}
          style={{ padding: '0.25rem 0.5rem', opacity: newer ? 1 : 0.35 }}
        >
          <ChevronRight size={14} />
        </button>
      </div>

      {data.expense_count === 0 ? (
        <div className="card" style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Nothing was recorded in {monthLabel(data.month)}.
        </div>
      ) : (
        <>
          <div className="card" style={{ padding: '1rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Group spent</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#ffffff' }}>{currency}{round(data.total)}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  {data.expense_count} {data.expense_count === 1 ? 'expense' : 'expenses'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Your share</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--accent-primary)' }}>{currency}{round(data.your_share)}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>you paid {currency}{round(data.your_paid)}</div>
              </div>
            </div>
            <div style={{ marginTop: '0.75rem', paddingTop: '0.65rem', borderTop: '1px solid var(--border-color)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {changeLabel}
              {data.settled_count > 0 && ` · ${currency}${round(data.settled_total)} settled up`}
            </div>
          </div>

          <div className="card" style={{ padding: '1rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.75rem' }}>
              Who paid, and whose it was
            </span>
            <Bars
              currency={currency}
              max={maxPaid}
              rows={data.people.flatMap(p => [
                { key: `${p.user_id}-paid`, label: p.name, value: p.paid, note: 'paid' },
                { key: `${p.user_id}-share`, label: '', value: p.share, note: 'their share', color: 'rgba(148, 163, 184, 0.65)' },
              ])}
            />
          </div>

          <div className="card" style={{ padding: '1rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.75rem' }}>
              Where it went
            </span>
            <Bars
              currency={currency}
              max={maxCategory}
              rows={data.categories.map(c => ({ key: c.category, label: c.label, value: c.total, note: `${c.percent}%` }))}
            />
          </div>

          <div className="card" style={{ padding: '1rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.75rem' }}>
              Biggest expenses
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
              {data.biggest.map(item => (
                <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', fontSize: '0.825rem' }}>
                  <span style={{ color: '#ffffff', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.description}
                  </span>
                  <span style={{ fontWeight: 700, color: 'var(--accent-primary)', flexShrink: 0 }}>{currency}{round(item.amount)}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
