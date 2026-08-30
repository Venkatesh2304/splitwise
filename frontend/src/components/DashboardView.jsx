import React, { useEffect, useState } from 'react';
import { useUser } from '../context/UserContext';
import { api } from '../services/api';
import { Wallet, Users, ArrowUpRight, ArrowDownRight, Plus } from 'lucide-react';

export default function DashboardView({ groups, onSelectGroup, onOpenAddGroup, onOpenAddExpense }) {
  const { activeUser } = useUser();
  const [groupDetailsMap, setGroupDetailsMap] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadAllGroupDetails() {
      setLoading(true);
      const details = {};
      for (const g of groups) {
        try {
          const detail = await api.getGroupDetail(g.id);
          details[g.id] = detail;
        } catch (e) {
          console.error(`Failed to fetch detail for group ${g.id}`, e);
        }
      }
      setGroupDetailsMap(details);
      setLoading(false);
    }
    if (groups.length > 0) {
      loadAllGroupDetails();
    } else {
      setLoading(false);
    }
  }, [groups]);

  let totalUserOwed = 0;   // Amount user gets back
  let totalUserOwes = 0;   // Amount user owes
  let totalSpending = 0;

  if (activeUser) {
    Object.values(groupDetailsMap).forEach(gDetail => {
      totalSpending += (gDetail.total_spending || 0);
      const netBals = gDetail.net_balances || {};
      const userBal = netBals[activeUser.id] ?? netBals[String(activeUser.id)] ?? 0;
      if (userBal > 0) {
        totalUserOwed += userBal;
      } else if (userBal < 0) {
        totalUserOwes += Math.abs(userBal);
      }
    });
  }

  const overallNet = totalUserOwed - totalUserOwes;

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
      {/* Top Banner Header */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        marginBottom: '1.5rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#ffffff', marginBottom: '0.15rem' }}>
              Welcome back, {activeUser ? activeUser.name.split(' ')[0] : 'Member'} 👋
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Financial summary across your active split groups.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', width: '100%' }}>
            <button className="btn btn-secondary btn-sm" onClick={onOpenAddGroup} style={{ flex: 1 }}>
              <Users size={16} />
              <span>Create Group</span>
            </button>
            <button className="btn btn-primary btn-sm" onClick={onOpenAddExpense} style={{ flex: 1 }}>
              <Plus size={16} />
              <span>Add Expense</span>
            </button>
          </div>
        </div>
      </div>

      {/* Overview Cards Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '1rem',
        marginBottom: '1.75rem'
      }}>
        {/* Card 1: Overall Balance */}
        <div className="card" style={{
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9))',
          borderLeft: `4px solid ${overallNet > 0 ? 'var(--color-positive)' : overallNet < 0 ? 'var(--color-negative)' : 'var(--text-muted)'}`
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              Overall Balance
            </span>
            <Wallet size={18} color={overallNet >= 0 ? '#10b981' : '#f43f5e'} />
          </div>
          <div style={{
            fontSize: '1.65rem',
            fontWeight: 800,
            color: overallNet > 0 ? 'var(--color-positive)' : overallNet < 0 ? 'var(--color-negative)' : 'var(--text-main)',
            marginBottom: '0.15rem'
          }}>
            {overallNet > 0 ? `+₹${Math.round(overallNet)}` : overallNet < 0 ? `-₹${Math.round(Math.abs(overallNet))}` : '₹0'}
          </div>
          <div style={{ fontSize: '0.775rem', color: 'var(--text-dim)' }}>
            {overallNet > 0 ? 'You get back money overall' : overallNet < 0 ? 'You owe money across groups' : 'Settled up'}
          </div>
        </div>

        {/* Card 2: You are Owed */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              You are Owed
            </span>
            <ArrowUpRight size={18} color="#10b981" />
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: 'var(--color-positive)', marginBottom: '0.15rem' }}>
            +₹{Math.round(totalUserOwed)}
          </div>
          <div style={{ fontSize: '0.775rem', color: 'var(--text-dim)' }}>
            Total friends owe you
          </div>
        </div>

        {/* Card 3: You Owe */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              You Owe
            </span>
            <ArrowDownRight size={18} color="#f43f5e" />
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: 'var(--color-negative)', marginBottom: '0.15rem' }}>
            -₹{Math.round(totalUserOwes)}
          </div>
          <div style={{ fontSize: '0.775rem', color: 'var(--text-dim)' }}>
            Total you owe friends
          </div>
        </div>
      </div>

      {/* Groups Grid */}
      <div style={{ marginBottom: '1rem' }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#ffffff', marginBottom: '0.85rem' }}>
          Active Groups ({groups.length})
        </h3>

        {groups.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '2rem 1rem' }}>
            <Users size={40} color="var(--text-dim)" style={{ marginBottom: '0.75rem' }} />
            <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.35rem' }}>No Groups Created Yet</h4>
            <button className="btn btn-primary btn-sm" onClick={onOpenAddGroup}>
              <Plus size={16} />
              <span>Create First Group</span>
            </button>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: '1rem'
          }}>
            {groups.map(group => {
              const detail = groupDetailsMap[group.id] || {};
              const netBals = detail.net_balances || {};
              const userBal = activeUser ? (netBals[activeUser.id] ?? netBals[String(activeUser.id)] ?? 0) : 0;
              const currency = group.currency || '$';

              return (
                <div
                  key={group.id}
                  className="card card-interactive"
                  onClick={() => onSelectGroup(group.id)}
                  style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                      <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#ffffff' }}>
                        {group.name}
                      </h4>
                      <span className="balance-tag neutral" style={{ fontSize: '0.725rem' }}>
                        {group.category}
                      </span>
                    </div>

                    <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                      {group.description || 'Shared expense group.'}
                    </p>
                  </div>

                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <div style={{ display: 'flex' }}>
                          {(group.members || []).slice(0, 3).map((m, idx) => (
                            <img
                              key={m.id}
                              src={m.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${m.name}`}
                              alt={m.name}
                              className="avatar"
                              style={{ width: '24px', height: '24px', marginLeft: idx > 0 ? '-8px' : 0 }}
                            />
                          ))}
                        </div>
                        <span style={{ fontSize: '0.725rem', color: 'var(--text-dim)' }}>
                          {group.members ? group.members.length : 0} members
                        </span>
                      </div>

                      <div>
                        {userBal > 0 ? (
                          <span className="balance-tag positive" style={{ fontSize: '0.725rem' }}>
                            + {currency}{Math.round(userBal)}
                          </span>
                        ) : userBal < 0 ? (
                          <span className="balance-tag negative" style={{ fontSize: '0.725rem' }}>
                            - {currency}{Math.round(Math.abs(userBal))}
                          </span>
                        ) : (
                          <span className="balance-tag neutral" style={{ fontSize: '0.725rem' }}>
                            settled
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
