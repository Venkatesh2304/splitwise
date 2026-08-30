import React, { useState } from 'react';
import { ArrowRight, CheckCircle2, Zap, Scale, HandCoins } from 'lucide-react';

export default function DebtGraphView({ group, members, netBalances, simplifiedDebts, currency, onTriggerSettle }) {
  const [viewMode, setViewMode] = useState('simplified'); // 'simplified' | 'individual'

  const memberMap = {};
  members.forEach(m => {
    memberMap[m.id] = m;
  });

  return (
    <div className="card" style={{ marginBottom: '2rem' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '1.5rem',
        paddingBottom: '1rem',
        borderBottom: '1px solid var(--border-color)'
      }}>
        <div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Zap size={20} color="var(--accent-primary)" />
            <span>Group Debt & Balance Matrix</span>
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Domain engine automatically calculates minimized transaction paths to settle group balances.
          </p>
        </div>

        {/* View Mode Switcher */}
        <div className="tab-group" style={{ width: 'auto' }}>
          <button
            className={`tab-btn ${viewMode === 'simplified' ? 'active' : ''}`}
            onClick={() => setViewMode('simplified')}
          >
            ⚡ Simplified Debts ({simplifiedDebts.length})
          </button>
          <button
            className={`tab-btn ${viewMode === 'individual' ? 'active' : ''}`}
            onClick={() => setViewMode('individual')}
          >
            ⚖️ Individual Balances
          </button>
        </div>
      </div>

      {viewMode === 'simplified' ? (
        <div>
          {simplifiedDebts.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)' }}>
              <CheckCircle2 size={40} color="var(--color-positive)" style={{ marginBottom: '0.75rem' }} />
              <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ffffff', marginBottom: '0.25rem' }}>
                Everyone in this group is settled up!
              </h4>
              <p style={{ fontSize: '0.85rem' }}>No outstanding debts to clear.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              {simplifiedDebts.map((st, idx) => {
                const debtor = memberMap[st.from_user_id] || { name: `User #${st.from_user_id}` };
                const creditor = memberMap[st.to_user_id] || { name: `User #${st.to_user_id}` };

                return (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '1rem 1.25rem',
                      backgroundColor: 'rgba(15, 23, 42, 0.6)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-color)',
                      transition: 'border-color 0.2s ease'
                    }}
                  >
                    {/* From Debtor to Creditor */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <img
                          src={debtor.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${debtor.name}`}
                          alt={debtor.name}
                          className="avatar"
                          style={{ width: '36px', height: '36px' }}
                        />
                        <span style={{ fontWeight: 600, color: '#ffffff', fontSize: '0.95rem' }}>
                          {debtor.name}
                        </span>
                      </div>

                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.25rem 0.75rem',
                        backgroundColor: 'var(--bg-surface)',
                        borderRadius: '9999px',
                        fontSize: '0.85rem',
                        color: 'var(--text-muted)'
                      }}>
                        <span>owes</span>
                        <ArrowRight size={16} color="var(--accent-primary)" />
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <img
                          src={creditor.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${creditor.name}`}
                          alt={creditor.name}
                          className="avatar"
                          style={{ width: '36px', height: '36px' }}
                        />
                        <span style={{ fontWeight: 600, color: '#ffffff', fontSize: '0.95rem' }}>
                          {creditor.name}
                        </span>
                      </div>
                    </div>

                    {/* Amount & Direct Settle Button */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                      <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-positive)' }}>
                        {currency}{st.amount.toFixed(2)}
                      </span>

                      <button
                        className="btn btn-outline-emerald btn-sm"
                        onClick={() => onTriggerSettle(debtor.id, creditor.id, st.amount)}
                      >
                        <HandCoins size={15} />
                        <span>Settle Debt</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        /* Individual Net Balances List */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '1rem' }}>
          {members.map(m => {
            const bal = netBalances[m.id] ?? netBalances[String(m.id)] ?? 0;
            return (
              <div
                key={m.id}
                style={{
                  padding: '1rem',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-color)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.85rem'
                }}
              >
                <img
                  src={m.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${m.name}`}
                  alt={m.name}
                  className="avatar"
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#ffffff' }}>
                    {m.name}
                  </div>
                  {bal > 0 ? (
                    <span className="balance-tag positive" style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>
                      gets back {currency}{bal.toFixed(2)}
                    </span>
                  ) : bal < 0 ? (
                    <span className="balance-tag negative" style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>
                      owes {currency}{Math.abs(bal).toFixed(2)}
                    </span>
                  ) : (
                    <span className="balance-tag neutral" style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>
                      settled up
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
