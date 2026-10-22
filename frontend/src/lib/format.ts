export function formatMoney(value: string | number, currency?: string | null, locale = 'fr-TN'): string {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  if (!currency) return new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 3 }).format(amount);
  try { return new Intl.NumberFormat(locale, { style: 'currency', currency, minimumFractionDigits: currency === 'TND' ? 3 : undefined, maximumFractionDigits: currency === 'TND' ? 3 : undefined }).format(amount); }
  catch { return `${new Intl.NumberFormat(locale).format(amount)} ${currency}`; }
}
export function initials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0] ?? '').join('').toUpperCase() || '·';
}
