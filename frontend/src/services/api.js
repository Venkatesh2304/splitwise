const getApiBaseUrl = () => {
  if (import.meta.env && import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const port = window.location.port;
    // In production frontend port 5001 -> backend port 5002
    if (port === '5001') {
      return `${window.location.protocol}//${hostname}:5002/api`;
    }
    return `${window.location.protocol}//${hostname}${port ? ':' + port : ''}/api`;
  }
  return 'http://localhost:5002/api';
};

export const API_BASE_URL = getApiBaseUrl();

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const config = {
    ...options,
    headers,
  };

  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }

  const response = await fetch(url, config);
  
  if (!response.ok) {
    let errData;
    try {
      errData = await response.json();
    } catch {
      errData = { message: response.statusText };
    }
    const message = typeof errData === 'object' ? JSON.stringify(errData) : errData;
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return null;
  }

  return await response.json();
}

export const api = {
  // Users
  getUsers: () => request('/users/'),
  createUser: (userData) => request('/users/', { method: 'POST', body: userData }),
  updateUser: (id, userData) => request(`/users/${id}/`, { method: 'PATCH', body: userData }),
  // Fetched only when a payment is about to be made, not with every user list
  getUpiId: (id) => request(`/users/${id}/upi/`),

  // Groups (userId brings back what that person hasn't seen yet)
  getGroups: (userId) => request(`/groups/${forUser(userId)}`),
  getGroupDetail: (id, userId) => request(`/groups/${id}/${forUser(userId)}`),
  markGroupSeen: (groupId, userId) => request(`/groups/${groupId}/seen/`, {
    method: 'POST',
    body: { user_id: userId }
  }),
  getGroupSummary: (groupId, month, userId) => {
    const params = new URLSearchParams();
    if (month) params.set('month', month);
    if (userId) params.set('user_id', userId);
    const query = params.toString();
    return request(`/groups/${groupId}/summary/${query ? `?${query}` : ''}`);
  },
  createGroup: (groupData) => request('/groups/', { method: 'POST', body: groupData }),
  addGroupMember: (groupId, userId) => request(`/groups/${groupId}/add_member/`, {
    method: 'POST',
    body: { user_id: userId }
  }),

  // Expenses (actor_id = who is making the change; they aren't notified about it)
  createExpense: (expenseData) => request('/expenses/', { method: 'POST', body: expenseData }),
  updateExpense: (id, expenseData) => request(`/expenses/${id}/`, { method: 'PUT', body: expenseData }),
  deleteExpense: (id, actorId) => request(`/expenses/${id}/${withActor(actorId)}`, { method: 'DELETE' }),

  // Settlements
  createSettlement: (settlementData) => request('/settlements/', { method: 'POST', body: settlementData }),
  deleteSettlement: (id, actorId) => request(`/settlements/${id}/${withActor(actorId)}`, { method: 'DELETE' }),

  // Push notifications
  getPushPublicKey: () => request('/push/public_key/'),
  pushSubscribe: (userId, subscription) => request('/push/subscribe/', {
    method: 'POST',
    body: { user_id: userId, subscription }
  }),
  pushUnsubscribe: (endpoint) => request('/push/unsubscribe/', { method: 'POST', body: { endpoint } }),
  pushTest: (userId) => request('/push/test/', { method: 'POST', body: { user_id: userId } }),

  // Ask someone to settle up (they get a notification)
  nudge: ({ actorId, userId, groupId, amount }) => request('/nudge/', {
    method: 'POST',
    body: { actor_id: actorId, user_id: userId, group_id: groupId, amount }
  }),
};

function withActor(actorId) {
  return actorId ? `?actor_id=${encodeURIComponent(actorId)}` : '';
}

function forUser(userId) {
  return userId ? `?user_id=${encodeURIComponent(userId)}` : '';
}
