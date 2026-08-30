import React, { useState } from 'react';
import BlinkitOrdersView from './BlinkitOrdersView';
import SwiggyOrdersView from './SwiggyOrdersView';
import { ShoppingBag, ShoppingCart } from 'lucide-react';

export default function GroceriesIntegrationView({ groceriesGroup, currentUser, onExpenseAdded }) {
  const [platform, setPlatform] = useState('swiggy'); // 'swiggy' | 'blinkit'

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      {/* Platform Switcher Header */}
      <div className="tab-group" style={{ marginBottom: '1rem' }}>
        <button
          className={`tab-btn ${platform === 'swiggy' ? 'active' : ''}`}
          onClick={() => setPlatform('swiggy')}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}
        >
          <ShoppingCart size={15} color="#fc8019" />
          <span>Swiggy Instamart 🛒</span>
        </button>
        <button
          className={`tab-btn ${platform === 'blinkit' ? 'active' : ''}`}
          onClick={() => setPlatform('blinkit')}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}
        >
          <ShoppingBag size={15} color="#f59e0b" />
          <span>Blinkit ⚡</span>
        </button>
      </div>

      {/* Platform Specific View */}
      {platform === 'swiggy' ? (
        <SwiggyOrdersView
          groceriesGroup={groceriesGroup}
          currentUser={currentUser}
          onExpenseAdded={onExpenseAdded}
        />
      ) : (
        <BlinkitOrdersView
          groceriesGroup={groceriesGroup}
          currentUser={currentUser}
          onExpenseAdded={onExpenseAdded}
        />
      )}
    </div>
  );
}
