// Helper to parse itemized products out of expense notes or description fallback
export function getExpenseProducts(exp) {
  if (!exp) return [];

  if (exp.notes) {
    try {
      const parsed = typeof exp.notes === 'string' ? JSON.parse(exp.notes) : exp.notes;
      if (parsed && typeof parsed === 'object') {
        if (Array.isArray(parsed.items) && parsed.items.length > 0) {
          return parsed.items;
        }
        if (Array.isArray(parsed.products) && parsed.products.length > 0) {
          return parsed.products;
        }
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch (e) {
      // not JSON
    }
  }

  if (Array.isArray(exp.items) && exp.items.length > 0) {
    return exp.items;
  }

  const desc = exp.description || '';
  const match = desc.match(/\((.*?)\)$/);
  if (match && match[1]) {
    const parts = match[1].split(' | ');
    return parts.map(p => {
      const sub = p.split(': ₹');
      return {
        name: sub[0] ? sub[0].trim() : p,
        price: sub[1] ? parseFloat(sub[1]) : 0,
        split_type: 'ALL',
        assigned_member_ids: []
      };
    });
  }

  return [];
}

/**
 * Unified source identifier for any expense across Blinkit, Swiggy, and Manual Itemized splits.
 */
export function getExpenseSource(exp) {
  if (!exp) {
    return {
      type: 'GENERAL',
      label: 'Expense',
      isPlatform: false,
      isItemized: false,
      platform: null,
      orderId: null,
      placedAt: null
    };
  }

  let notesObj = null;
  if (exp.notes) {
    try {
      notesObj = typeof exp.notes === 'string' ? JSON.parse(exp.notes) : exp.notes;
    } catch (e) {
      notesObj = null;
    }
  }

  const platform = notesObj?.platform || null;
  let orderId = notesObj?.order_id || null;
  const placedAt = notesObj?.placed_at || null;
  const splitMode = notesObj?.split_mode || null;

  if (!orderId && exp.description) {
    const m = exp.description.match(/#(\d+)/);
    if (m) orderId = m[1];
  }

  const isPlatform = Boolean(platform);
  const hasItems = getExpenseProducts(exp).length > 0;
  const isItemized = exp.split_type === 'ITEMS' || splitMode === 'ITEMIZED' || isPlatform || hasItems;

  let type = 'GENERAL';
  let label = 'Expense';

  if (platform) {
    if (/blinkit/i.test(platform)) {
      type = 'BLINKIT';
      label = 'Blinkit';
    } else if (/swiggy/i.test(platform)) {
      type = 'SWIGGY';
      label = 'Swiggy Instamart';
    } else {
      type = 'PLATFORM';
      label = platform;
    }
  } else if (isItemized) {
    type = 'MANUAL';
    label = 'Itemized Bill';
  }

  return {
    type,
    label,
    isPlatform,
    isItemized,
    platform,
    orderId,
    placedAt
  };
}

/**
 * Calculates item shares and proportional fee distribution for any itemized expense.
 * Shared implementation for Blinkit, Swiggy, and Manual Itemized expenses.
 */
export function calculateItemBreakdown(exp, members = [], myUserId = null) {
  const products = getExpenseProducts(exp);
  if (products.length === 0) {
    return {
      items: [],
      totalProductsValue: 0,
      totalCommonFees: 0,
      mySubtotalProducts: 0,
      myFeeShare: 0,
      myTotalShare: 0,
    };
  }

  const allMemberIds = members.map(m => m.id);
  const fallbackIds = allMemberIds.length > 0
    ? allMemberIds
    : ((exp.shares || []).map(s => s.user?.id || s.user_id).filter(Boolean));

  const buyerObj = exp.created_by;
  const buyerId = buyerObj ? (typeof buyerObj === 'object' ? buyerObj.id : buyerObj) : null;
  const personalFallbackId = buyerId || (fallbackIds.length > 0 ? fallbackIds[0] : null);

  let totalProductsValue = 0;
  let mySubtotalProducts = 0;

  const decoratedItems = products.map((item) => {
    const prodValue = parseFloat(item.price) || 0;
    totalProductsValue += prodValue;

    const mode = item.split_type || 'SPECIFIC';
    const listedIds = (item.assigned_member_ids || []).map(Number);

    let assigned = [];
    if (mode === 'ALL') {
      assigned = fallbackIds;
    } else if (mode === 'PERSONAL') {
      assigned = listedIds.length > 0 ? [listedIds[0]] : (personalFallbackId ? [personalFallbackId] : fallbackIds);
    } else {
      assigned = listedIds.length > 0 ? listedIds : fallbackIds;
    }

    const isAssignedToMe = myUserId ? assigned.map(Number).includes(Number(myUserId)) : false;
    const myProductShare = (isAssignedToMe && assigned.length > 0) ? (prodValue / assigned.length) : 0;
    mySubtotalProducts += myProductShare;

    // Names of assigned members
    const assignedNames = (item.assigned_names && item.assigned_names.length > 0)
      ? item.assigned_names
      : members.filter(m => assigned.includes(m.id)).map(m => (m.name || '').split(' ')[0]);

    let badgeText = 'Everyone';
    if (mode === 'PERSONAL') {
      const pName = buyerObj && typeof buyerObj === 'object' && buyerObj.name ? buyerObj.name.split(' ')[0] : 'Self';
      badgeText = `Personal (${pName})`;
    } else if (mode === 'SPECIFIC' || (assigned.length > 0 && assigned.length < fallbackIds.length)) {
      badgeText = `Chosen (${assignedNames.length > 0 ? assignedNames.join(', ') : `${assigned.length} members`})`;
    }

    return {
      ...item,
      price: prodValue,
      quantity: item.quantity || 1,
      assignedIds: assigned,
      assignedNames,
      badgeText,
      myShare: myProductShare,
      isZeroShare: myProductShare === 0,
    };
  });

  const expAmount = parseFloat(exp.amount) || totalProductsValue;
  const totalCommonFees = Math.max(0, expAmount - totalProductsValue);
  const myFeeShare = totalProductsValue > 0 ? (mySubtotalProducts / totalProductsValue) * totalCommonFees : 0;
  const myTotalShare = mySubtotalProducts + myFeeShare;

  return {
    items: decoratedItems,
    totalProductsValue,
    totalCommonFees,
    mySubtotalProducts,
    myFeeShare,
    myTotalShare,
  };
}

export const FOOD_KEYWORD_RULES = [
  // Multi-word specific items
  [/\bgroundnut oil\b/i, 'Groundnut Oil'],
  [/\bmustard oil\b/i, 'Mustard Oil'],
  [/\bsunflower oil\b/i, 'Sunflower Oil'],
  [/\brefined oil\b/i, 'Cooking Oil'],
  [/\bcoconut oil\b/i, 'Coconut Oil'],
  [/\blady finger\b|\bbhindi\b/i, 'Lady Finger'],
  [/\bfrench fries\b/i, 'Fries'],
  [/\bsweet corn\b/i, 'Sweet Corn'],
  [/\bbiryani kit\b/i, 'Biryani Kit'],
  [/\bdark fantasy\b/i, 'Biscuits'],
  [/\b(idli\s*&\s*dosa|idli|dosa)\s*batter\b/i, 'Batter'],
  [/\bbatter\b/i, 'Batter'],
  [/\bred bull\b/i, 'Energy Drink'],
  [/\braw pressery\b/i, 'Juice'],
  [/\bgarlic bread\b/i, 'Garlic Bread'],
  [/\bice cream\b/i, 'Ice Cream'],
  [/\bpeanut butter\b/i, 'Peanut Butter'],

  // Core single-word items
  [/\bchicken\b/i, 'Chicken'],
  [/\bmutton\b/i, 'Mutton'],
  [/\bfish\b/i, 'Fish'],
  [/\bprawns?\b/i, 'Prawns'],
  [/\bsausages?\b/i, 'Sausages'],
  [/\bmeat\b/i, 'Meat'],
  [/\beggs?\b/i, 'Eggs'],
  [/\bmilk\b/i, 'Milk'],
  [/\b(curd|dahi|yogurt)\b/i, 'Curd'],
  [/\bbread\b/i, 'Bread'],
  [/\b(pav|bun|croissant)\b/i, 'Bakery'],
  [/\b(banana|kela)s?\b/i, 'Banana'],
  [/\b(onion|pyaaz)s?\b/i, 'Onion'],
  [/\b(potato|aloo)s?\b/i, 'Potato'],
  [/\b(tomato|tamatar)s?\b/i, 'Tomato'],
  [/\bghee\b/i, 'Ghee'],
  [/\boil\b/i, 'Oil'],
  [/\b(rice|sonamasuri|basmati)\b/i, 'Rice'],
  [/\bpoha\b/i, 'Poha'],
  [/\b(dal|toor|chana|rajma|moong)\b/i, 'Dal'],
  [/\bsugar\b/i, 'Sugar'],
  [/\bsalt\b/i, 'Salt'],
  [/\b(atta|flour|maida|besan)\b/i, 'Atta'],
  [/\b(masala|spices?|turmeric|pepper|jeera|cumin)\b/i, 'Spices'],
  [/\bpaneer\b/i, 'Paneer'],
  [/\bcheese\b/i, 'Cheese'],
  [/\bbuttermilk\b/i, 'Buttermilk'],
  [/\bbutter\b/i, 'Butter'],
  [/\bgranola\b/i, 'Granola'],
  [/\bmuesli\b/i, 'Muesli'],
  [/\boats\b/i, 'Oats'],
  [/\bcorn flakes\b/i, 'Cereals'],
  [/\b(chips|crisps|kurkure|nachos)\b/i, 'Chips'],
  [/\b(biscuits?|cookies?)\b/i, 'Biscuits'],
  [/\bchocolates?\b/i, 'Chocolate'],
  [/\b(pizza|burger|sandwich|momos)\b/i, 'Snacks'],
  [/\b(noodles?|maggi|pasta)\b/i, 'Noodles'],
  [/\bjuice\b/i, 'Juice'],
  [/\bcoffee\b/i, 'Coffee'],
  [/\btea\b/i, 'Tea'],
  [/\b(detergent|surf excel|harpic|vim)\b/i, 'Cleaning'],
  [/\b(shampoo|soap|shower gel|body\s*wash|facewash)\b/i, 'Personal Care'],

  // Specific vegetables & fruits
  [/\b(carrot|beans|capsicum|cucumber|palak|spinach|mushroom|cauliflower|cabbage|peas|matar|ginger|garlic|coriander|chilli|chili|lemon)\b/i, 'Vegetables'],
  [/\b(apple|pomegranate|orange|watermelon|papaya|grapes|avocado)\b/i, 'Fruits'],

  // Brand fallbacks
  [/\bmeatizon\b/i, 'Chicken'],
  [/\blicious\b/i, 'Chicken'],
  [/\bfreshtohome\b/i, 'Meat'],
];

export function extractTopProductKeyword(productName) {
  if (!productName) return 'Groceries';
  for (const [pattern, display] of FOOD_KEYWORD_RULES) {
    if (pattern.test(productName)) {
      return display;
    }
  }
  const words = productName.match(/[A-Za-z]+/g) || [];
  const ignore = new Set(['pack', 'pcs', 'gm', 'g', 'kg', 'ml', 'l', 'fresh', 'premium', 'daily', 'delight', 'pure', 'classic']);
  const filtered = words.filter(w => !ignore.has(w.toLowerCase()) && w.length > 1);
  if (filtered.length > 0) {
    return filtered.slice(0, 2).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
  }
  return 'Groceries';
}

export function deriveOrderTitle(platformName, items, orderId) {
  const plat = (platformName || '').toLowerCase();
  const prefix = plat.includes('swiggy') ? 'Swiggy' : (plat.includes('blinkit') ? 'Blinkit' : (platformName || 'Order'));

  if (Array.isArray(items) && items.length > 0) {
    const sorted = [...items].sort((a, b) => (parseFloat(b.price) || 0) - (parseFloat(a.price) || 0));
    for (const it of sorted) {
      if (it && it.name) {
        const kw = extractTopProductKeyword(it.name);
        if (kw) return `${prefix}: ${kw}`;
      }
    }
  }

  if (orderId) return `${prefix}: Order #${orderId}`;
  return `${prefix}: Groceries`;
}

