import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const UserContext = createContext();

export function UserProvider({ children }) {
  const [users, setUsers] = useState([]);
  const [activeUser, setActiveUser] = useState(() => {
    const saved = localStorage.getItem('splitwise_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(true);

  const refreshUsers = async () => {
    try {
      setLoading(true);
      const data = await api.getUsers();
      setUsers(data);
      const saved = localStorage.getItem('splitwise_user');
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          const matched = data.find(u => u.id === parsed.id || u.username === parsed.username);
          if (matched) setActiveUser(matched);
        } catch (e) {}
      }
    } catch (err) {
      console.error('Failed to fetch users:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUsers();
  }, []);

  return (
    <UserContext.Provider value={{ users, activeUser, setActiveUser, refreshUsers, loading }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
