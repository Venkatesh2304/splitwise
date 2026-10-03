// A UPI app can only be opened from a phone; elsewhere we show the id to copy instead
export const canOpenUpiApp = () => {
  if (typeof navigator === 'undefined') return false;
  return /Android|iPhone|iPad/i.test(navigator.userAgent) || navigator.maxTouchPoints > 1;
};

export function upiPayLink({ upiId, name, amount, note }) {
  const params = new URLSearchParams({
    pa: upiId,
    pn: name || '',
    am: Number(amount).toFixed(2),
    cu: 'INR',
    tn: note || 'Splitwise settle-up',
  });
  return `upi://pay?${params.toString()}`;
}
