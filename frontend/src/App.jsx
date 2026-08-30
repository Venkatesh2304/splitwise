import React, { useState, useEffect } from 'react';
import { UserProvider } from './context/UserContext';
import { api } from './services/api';

import Header from './components/Header';
import Sidebar from './components/Sidebar';
import DashboardView from './components/DashboardView';
import GroupDetailView from './components/GroupDetailView';
import GroceriesIntegrationView from './components/GroceriesIntegrationView';
import LoginScreen from './components/LoginScreen';

import AddGroupModal from './components/AddGroupModal';
import AddExpenseModal from './components/AddExpenseModal';
import SettleUpModal from './components/SettleUpModal';
import UserModal from './components/UserModal';
import AddMemberToGroupModal from './components/AddMemberToGroupModal';

import { LayoutDashboard, ShoppingBag, ShoppingCart, LogOut, Plus } from 'lucide-react';

function AppContent() {
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem('splitwise_user');
    return saved ? JSON.parse(saved) : null;
  });

  const [demoUsers, setDemoUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [activeGroupId, setActiveGroupId] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard'); // 'dashboard' | 'blinkit'

  // Modal visibility states
  const [isAddGroupOpen, setIsAddGroupOpen] = useState(false);
  const [isAddExpenseOpen, setIsAddExpenseOpen] = useState(false);
  const [isSettleUpOpen, setIsSettleUpOpen] = useState(false);
  const [isAddUserOpen, setIsAddUserOpen] = useState(false);
  const [isAddMemberToGroupOpen, setIsAddMemberToGroupOpen] = useState(false);

  // Contextual data for modals
  const [selectedExpenseGroup, setSelectedExpenseGroup] = useState(null);
  const [settleModalData, setSettleModalData] = useState({
    group: null,
    payerId: null,
    payeeId: null,
    amount: ''
  });
  const [activeGroupData, setActiveGroupData] = useState(null);

  const fetchUsers = async () => {
    try {
      const data = await api.getUsers();
      setDemoUsers(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchGroups = async () => {
    try {
      const data = await api.getGroups();
      setGroups(data);
    } catch (err) {
      console.error('Failed to fetch groups:', err);
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchGroups();
  }, []);

  const handleLoginSuccess = (userObj) => {
    setCurrentUser(userObj);
    localStorage.setItem('splitwise_user', JSON.stringify(userObj));
    fetchGroups();
  };

  const handleLogout = () => {
    setCurrentUser(null);
    localStorage.removeItem('splitwise_user');
  };

  const handleGroupSelect = (id) => {
    setActiveGroupId(id);
    setActiveTab('dashboard');
  };

  const handleDashboardSelect = () => {
    setActiveGroupId(null);
    setActiveTab('dashboard');
  };

  const handleOpenAddExpense = (targetGroup = null) => {
    setSelectedExpenseGroup(targetGroup);
    setIsAddExpenseOpen(true);
  };

  const handleOpenSettleUp = (group = null, payerId = null, payeeId = null, amount = '') => {
    const targetGroup = group || (activeGroupId ? groups.find(g => g.id === activeGroupId) : groups[0]);
    setSettleModalData({
      group: targetGroup,
      payerId,
      payeeId,
      amount
    });
    setIsSettleUpOpen(true);
  };

  const handleOpenAddMemberToGroup = (groupData) => {
    setActiveGroupData(groupData);
    setIsAddMemberToGroupOpen(true);
  };

  if (!currentUser) {
    return <LoginScreen onLoginSuccess={handleLoginSuccess} demoUsers={demoUsers} />;
  }

  const activeGroup = groups.find(g => g.id === activeGroupId);
  const groceriesGroup = groups.find(g => g.name.toLowerCase().includes('groceries')) || (groups.length > 0 ? groups[0] : null);

  return (
    <div className="app-container">
      <Header
        currentUser={currentUser}
        activeTab={activeTab}
        onTabChange={(tab) => {
          setActiveTab(tab);
          if (tab === 'blinkit') setActiveGroupId(null);
        }}
        onOpenAddGroup={() => setIsAddGroupOpen(true)}
        onOpenAddExpense={() => handleOpenAddExpense(activeGroup || groceriesGroup)}
        onLogout={handleLogout}
      />

      <div className="app-main">
        <Sidebar
          groups={groups}
          activeGroupId={activeGroupId}
          onSelectGroup={handleGroupSelect}
          onSelectDashboard={handleDashboardSelect}
          onOpenAddGroup={() => setIsAddGroupOpen(true)}
        />

        <main className="content-area" style={{ paddingBottom: '5rem' }}>
          {activeTab === 'blinkit' ? (
            <GroceriesIntegrationView
              groceriesGroup={groceriesGroup}
              currentUser={currentUser}
              onExpenseAdded={() => fetchGroups()}
            />
          ) : activeGroupId === null ? (
            <DashboardView
              groups={groups}
              onSelectGroup={handleGroupSelect}
              onOpenAddGroup={() => setIsAddGroupOpen(true)}
              onOpenAddExpense={() => handleOpenAddExpense(null)}
            />
          ) : (
            <GroupDetailView
              key={activeGroupId}
              groupId={activeGroupId}
              currentUser={currentUser}
              onBack={handleDashboardSelect}
              onOpenAddExpense={(g) => handleOpenAddExpense(g)}
              onOpenSettleUp={(g, p1, p2, amt) => handleOpenSettleUp(g, p1, p2, amt)}
              onOpenAddMember={(g) => handleOpenAddMemberToGroup(g)}
              onOpenBlinkit={() => setActiveTab('blinkit')}
            />
          )}
        </main>
      </div>

      {/* Mobile Bottom Navigation Bar */}
      <nav style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: '60px',
        backgroundColor: 'rgba(15, 23, 42, 0.98)',
        borderTop: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-around',
        zIndex: 50
      }}>
        <button
          onClick={handleDashboardSelect}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '2px',
            background: 'none',
            border: 'none',
            color: activeTab === 'dashboard' && activeGroupId === null ? 'var(--accent-primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            fontSize: '0.7rem',
            fontWeight: 600
          }}
        >
          <LayoutDashboard size={20} />
          <span>Dashboard</span>
        </button>

        {groceriesGroup && (
          <button
            onClick={() => handleGroupSelect(groceriesGroup.id)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '2px',
              background: 'none',
              border: 'none',
              color: activeGroupId === groceriesGroup.id ? 'var(--accent-primary)' : 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '0.7rem',
              fontWeight: 600
            }}
          >
            <ShoppingCart size={20} />
            <span>Groceries 🛒</span>
          </button>
        )}

        <button
          onClick={() => { setActiveTab('blinkit'); setActiveGroupId(null); }}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '2px',
            background: 'none',
            border: 'none',
            color: activeTab === 'blinkit' ? '#fc8019' : 'var(--text-muted)',
            cursor: 'pointer',
            fontSize: '0.7rem',
            fontWeight: 600
          }}
        >
          <ShoppingBag size={20} />
          <span>Quick Grocery Apps 🛒</span>
        </button>
      </nav>

      {/* Modals */}
      <AddGroupModal
        isOpen={isAddGroupOpen}
        onClose={() => setIsAddGroupOpen(false)}
        onGroupCreated={(newGroup) => {
          fetchGroups();
          setActiveGroupId(newGroup.id);
        }}
      />

      <AddExpenseModal
        isOpen={isAddExpenseOpen}
        onClose={() => setIsAddExpenseOpen(false)}
        groups={groups}
        activeGroup={selectedExpenseGroup || activeGroup || groceriesGroup}
        onExpenseAdded={() => {
          fetchGroups();
          const curr = activeGroupId;
          setActiveGroupId(null);
          setTimeout(() => setActiveGroupId(curr), 50);
        }}
      />

      <SettleUpModal
        isOpen={isSettleUpOpen}
        onClose={() => setIsSettleUpOpen(false)}
        group={settleModalData.group || groceriesGroup}
        initialPayerId={settleModalData.payerId}
        initialPayeeId={settleModalData.payeeId}
        initialAmount={settleModalData.amount}
        onSettlementRecorded={() => {
          fetchGroups();
          const curr = activeGroupId;
          setActiveGroupId(null);
          setTimeout(() => setActiveGroupId(curr), 50);
        }}
      />

      <UserModal
        isOpen={isAddUserOpen}
        onClose={() => setIsAddUserOpen(false)}
      />

      <AddMemberToGroupModal
        isOpen={isAddMemberToGroupOpen}
        onClose={() => setIsAddMemberToGroupOpen(false)}
        group={activeGroupData}
        onMemberAdded={() => {
          fetchGroups();
          const curr = activeGroupId;
          setActiveGroupId(null);
          setTimeout(() => setActiveGroupId(curr), 50);
        }}
      />
    </div>
  );
}

export default function App() {
  return (
    <UserProvider>
      <AppContent />
    </UserProvider>
  );
}
