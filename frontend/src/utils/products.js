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
        split_type: 'ALL'
      };
    });
  }

  return [];
}
