import React from 'react';
import { Plus, X } from 'lucide-react';

const round2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100;
const firstName = (member) => (member.name || '').split(' ')[0];

export const blankItem = (memberIds) => ({
  key: `item-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  name: '',
  price: '',
  assigned: [...memberIds],
});

/** Mirrors split_items() on the server, for the live preview only — the server
 *  recomputes on save and its answer is the one that's stored. */
export function previewShares(total, items, memberIds, remainderTo) {
  const subtotals = Object.fromEntries(memberIds.map(id => [id, 0]));
  let itemsTotal = 0;

  items.forEach((item) => {
    const price = parseFloat(item.price) || 0;
    itemsTotal += price;
    const targets = item.assigned.length ? item.assigned : memberIds;
    targets.forEach((id) => {
      if (id in subtotals) subtotals[id] += price / targets.length;
    });
  });

  const charges = Math.max(0, round2(total - itemsTotal));
  const subtotalSum = Object.values(subtotals).reduce((a, b) => a + b, 0) || 1;

  const owed = {};
  memberIds.forEach((id) => {
    const fee = charges > 0 ? (subtotals[id] / subtotalSum) * charges : 0;
    owed[id] = round2(subtotals[id] + fee);
  });

  const difference = round2(total - Object.values(owed).reduce((a, b) => a + b, 0));
  if (difference !== 0 && remainderTo in owed) owed[remainderTo] = round2(owed[remainderTo] + difference);
  return owed;
}

export default function ItemsEditor({ members, items, onItemsChange, charges, onChargesChange, currency, payerId }) {
  const memberIds = members.map(m => m.id);

  const update = (index, changes) => {
    const next = [...items];
    next[index] = { ...next[index], ...changes };
    onItemsChange(next);
  };

  const toggleMember = (index, memberId) => {
    const current = items[index].assigned;
    update(index, {
      assigned: current.includes(memberId) ? current.filter(id => id !== memberId) : [...current, memberId],
    });
  };

  const itemsTotal = items.reduce((sum, item) => sum + (parseFloat(item.price) || 0), 0);
  const total = round2(itemsTotal + (parseFloat(charges) || 0));
  const preview = previewShares(total, items, memberIds, payerId || memberIds[0]);

  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {items.map((item, index) => {
          const price = parseFloat(item.price) || 0;
          const each = item.assigned.length ? price / item.assigned.length : 0;
          return (
            <div
              key={item.key}
              style={{
                padding: '0.6rem 0.7rem',
                backgroundColor: 'rgba(15, 23, 42, 0.5)',
                border: `1px solid ${item.assigned.length === 0 ? 'var(--color-negative)' : 'var(--border-color)'}`,
                borderRadius: 'var(--radius-md)'
              }}
            >
              <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                <input
                  className="form-input"
                  placeholder="Item"
                  value={item.name}
                  onChange={(e) => update(index, { name: e.target.value })}
                  style={{ flex: '1 1 auto', minWidth: 0, padding: '0.35rem 0.55rem', fontSize: '0.825rem' }}
                />
                <input
                  className="form-input"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0"
                  value={item.price}
                  onChange={(e) => update(index, { price: e.target.value })}
                  style={{ width: '88px', flexShrink: 0, padding: '0.35rem 0.55rem', fontSize: '0.825rem' }}
                />
                <button
                  type="button"
                  onClick={() => onItemsChange(items.filter((_, i) => i !== index))}
                  title="Remove item"
                  style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', padding: '0.2rem', flexShrink: 0 }}
                >
                  <X size={15} />
                </button>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginTop: '0.45rem', alignItems: 'center' }}>
                {members.map((member) => {
                  const on = item.assigned.includes(member.id);
                  return (
                    <button
                      key={member.id}
                      type="button"
                      onClick={() => toggleMember(index, member.id)}
                      style={{
                        fontSize: '0.725rem',
                        fontWeight: 600,
                        padding: '0.15rem 0.5rem',
                        borderRadius: '999px',
                        cursor: 'pointer',
                        color: on ? '#0f172a' : 'var(--text-muted)',
                        backgroundColor: on ? 'var(--accent-primary)' : 'transparent',
                        border: `1px solid ${on ? 'var(--accent-primary)' : 'var(--border-color)'}`
                      }}
                    >
                      {firstName(member)}
                    </button>
                  );
                })}
                <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginLeft: 'auto' }}>
                  {item.assigned.length === 0
                    ? 'nobody yet'
                    : `${currency}${each.toFixed(2)} each`}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <button
        type="button"
        className="btn btn-secondary btn-sm"
        onClick={() => onItemsChange([...items, blankItem(memberIds)])}
        style={{ marginTop: '0.55rem' }}
      >
        <Plus size={14} />
        <span>Add item</span>
      </button>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.85rem' }}>
        <label className="form-label" style={{ marginBottom: 0, flex: 1 }}>Tax & other charges</label>
        <input
          className="form-input"
          type="number"
          step="0.01"
          min="0"
          placeholder="0"
          value={charges}
          onChange={(e) => onChargesChange(e.target.value)}
          style={{ width: '110px', padding: '0.35rem 0.55rem', fontSize: '0.825rem' }}
        />
      </div>
      <div style={{ fontSize: '0.725rem', color: 'var(--text-dim)', marginTop: '0.3rem' }}>
        Shared out in proportion to what each person's items came to.
      </div>

      {items.length > 0 && (
        <div style={{
          marginTop: '0.85rem',
          padding: '0.6rem 0.75rem',
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)'
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.4rem' }}>
            Each person owes
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {members.map((member) => (
              <div key={member.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                <span style={{ color: '#ffffff' }}>{member.name}{member.id === payerId ? ' (paid)' : ''}</span>
                <span style={{ color: preview[member.id] > 0 ? 'var(--accent-primary)' : 'var(--text-dim)', fontWeight: 600 }}>
                  {currency}{(preview[member.id] || 0).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
          <div style={{ marginTop: '0.45rem', paddingTop: '0.4rem', borderTop: '1px solid var(--border-color)', fontSize: '0.775rem', color: 'var(--text-muted)' }}>
            {items.length} {items.length === 1 ? 'item' : 'items'} {currency}{itemsTotal.toFixed(2)}
            {(parseFloat(charges) || 0) > 0 && ` + ${currency}${(parseFloat(charges) || 0).toFixed(2)} charges`}
            {' = '}
            <strong style={{ color: '#ffffff' }}>{currency}{total.toFixed(2)}</strong>
          </div>
        </div>
      )}
    </div>
  );
}
