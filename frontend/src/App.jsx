import React, { useState, useEffect, useCallback } from 'react';
import { UserProvider, useUser } from './context/UserContext';
import { api } from './services/api';
import { getPushState, enablePush, disablePush, resyncPush } from './services/push';

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

// A notification opens /?group=<id>&expense=<id>
function readDeepLink(url) {
  try {
    const params = new URL(url, window.location.origin).searchParams;
    const group = parseInt(params.get('group'), 10);
    const expense = parseInt(params.get('expense'), 10);
    return { groupId: Number.isNaN(group) ? null : group, expenseId: Number.isNaN(expense) ? null : expense };
  } catch {
    return { groupId: null, expenseId: null };
  }
}

function AppContent() {
  const { setActiveUser } = useUser();
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem('splitwise_user');
    return saved ? JSON.parse(saved) : null;
  });

  const [demoUsers, setDemoUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [initialLink] = useState(() => readDeepLink(window.location.href));
  const [activeGroupId, setActiveGroupId] = useState(initialLink.groupId);
  const [activeTab, setActiveTab] = useState('dashboard'); // 'dashboard' | 'blinkit'
  const [focusExpenseId, setFocusExpenseId] = useState(initialLink.expenseId);
  const [refreshToken, setRefreshToken] = useState(0);
  const [pushState, setPushState] = useState('checking');
  // When each group was last seen, captured the first time it's opened in this session.
  // Marking the group seen on the server happens straight away, but the page keeps
  // comparing against this, so highlights last the whole visit instead of blinking out.
  const [seenBaselines, setSeenBaselines] = useState({});

  // Modal visibility states
  const [isAddGroupOpen, setIsAddGroupOpen] = useState(false);
  const [isAddExpenseOpen, setIsAddExpenseOpen] = useState(false);
  const [isSettleUpOpen, setIsSettleUpOpen] = useState(false);
  const [isAddUserOpen, setIsAddUserOpen] = useState(false);
  const [isAddMemberToGroupOpen, setIsAddMemberToGroupOpen] = useState(false);

  // Contextual data for modals
  const [selectedExpenseGroup, setSelectedExpenseGroup] = useState(null);
  const [editingExpense, setEditingExpense] = useState(null);
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

  const fetchGroups = async (userId) => {
    try {
      const data = await api.getGroups(userId ?? currentUser?.id);
      setGroups(data);
    } catch (err) {
      console.error('Failed to fetch groups:', err);
    }
  };

  // Reload groups and whichever group is on screen
  const refreshAll = useCallback(() => {
    fetchGroups();
    setRefreshToken((t) => t + 1);
  }, []);

  useEffect(() => {
    fetchUsers();
    fetchGroups();
    if (initialLink.groupId !== null) {
      window.history.replaceState(null, '', window.location.pathname);
    }
  }, []);

  // Notifications: current state, and keep this device filed under the logged-in user
  useEffect(() => {
    if (!currentUser) return;
    getPushState().then(setPushState);
    resyncPush(currentUser);
  }, [currentUser?.id]);

  // Messages from the service worker: a push arrived, or a notification was tapped
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;
    const onMessage = (event) => {
      const msg = event.data || {};
      if (msg.type === 'splitwise:changed') {
        refreshAll();
      } else if (msg.type === 'splitwise:open') {
        const link = readDeepLink(msg.url);
        if (link.groupId !== null) {
          setActiveTab('dashboard');
          setActiveGroupId(link.groupId);
          setFocusExpenseId(link.expenseId);
        }
        refreshAll();
      }
    };
    navigator.serviceWorker.addEventListener('message', onMessage);
    return () => navigator.serviceWorker.removeEventListener('message', onMessage);
  }, [refreshAll]);

  const handleEnablePush = async () => {
    const state = await enablePush(currentUser);
    setPushState(state);
    return 'Done. Tap “Send test” to check it works.';
  };

  const handleDisablePush = async () => {
    await disablePush();
    setPushState(await getPushState());
    return 'Notifications are off for this device.';
  };

  const handleTestPush = async () => {
    const res = await api.pushTest(currentUser.id);
    if (!res.devices) throw new Error('This device isn’t registered. Turn notifications off and on again.');
    if (!res.sent) throw new Error('The push service rejected it. Turn notifications off and on again.');
    return `Sent. It should appear in a few seconds${res.devices > 1 ? ` (on all ${res.devices} of your devices)` : ''}.`;
  };

  // Called by the group screen once it knows when this person last looked
  const handleGroupOpened = useCallback((groupId, lastSeenAt) => {
    setSeenBaselines((current) => {
      if (groupId in current) return current;           // already fixed for this visit
      api.markGroupSeen(groupId, currentUser?.id)
        .then(() => fetchGroups())                      // clears the badge on the dashboard
        .catch((err) => console.error('Could not mark the group as seen:', err));
      return { ...current, [groupId]: lastSeenAt || null };
    });
  }, [currentUser?.id]);

  const handleLoginSuccess = (userObj) => {
    setCurrentUser(userObj);
    if (setActiveUser) setActiveUser(userObj);
    localStorage.setItem('splitwise_user', JSON.stringify(userObj));
    setSeenBaselines({});
    fetchGroups(userObj.id);
  };

  const handleLogout = () => {
    // A shared phone shouldn't keep receiving the previous user's notifications
    disablePush();
    setPushState('off');
    setSeenBaselines({});
    setCurrentUser(null);
    if (setActiveUser) setActiveUser(null);
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
    setEditingExpense(null);
    setSelectedExpenseGroup(targetGroup);
    setIsAddExpenseOpen(true);
  };

  const handleOpenEditExpense = (expense, group) => {
    setEditingExpense(expense);
    setSelectedExpenseGroup(group);
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
        pushState={pushState}
        onEnablePush={handleEnablePush}
        onDisablePush={handleDisablePush}
        onTestPush={handleTestPush}
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
              pushState={pushState}
              onEnablePush={handleEnablePush}
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
              onEditExpense={(exp, g) => handleOpenEditExpense(exp, g)}
              seenBaseline={seenBaselines[activeGroupId]}
              onGroupOpened={handleGroupOpened}
              refreshToken={refreshToken}
              focusExpenseId={focusExpenseId}
              onFocusHandled={() => setFocusExpenseId(null)}
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
        onClose={() => { setIsAddExpenseOpen(false); setEditingExpense(null); }}
        groups={groups}
        activeGroup={selectedExpenseGroup || activeGroup || groceriesGroup}
        editingExpense={editingExpense}
        onExpenseAdded={refreshAll}
      />

      <SettleUpModal
        isOpen={isSettleUpOpen}
        onClose={() => setIsSettleUpOpen(false)}
        group={settleModalData.group || groceriesGroup}
        initialPayerId={settleModalData.payerId}
        initialPayeeId={settleModalData.payeeId}
        initialAmount={settleModalData.amount}
        onSettlementRecorded={refreshAll}
      />

      <UserModal
        isOpen={isAddUserOpen}
        onClose={() => setIsAddUserOpen(false)}
      />

      <AddMemberToGroupModal
        isOpen={isAddMemberToGroupOpen}
        onClose={() => setIsAddMemberToGroupOpen(false)}
        group={activeGroupData}
        onMemberAdded={refreshAll}
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
