export const CAT_COLORS: Record<string, string> = {
  'Dining & Drinks': '#f87171',
  'Groceries & Essentials': '#34d399',
  Transport: '#60a5fa',
  Shopping: '#fbbf24',
  Travel: '#a78bfa',
  'Subscriptions & Services': '#f472b6',
  Entertainment: '#22d3ee',
  'Fees & Charges': '#a3e635',
  Uncategorized: '#71717a',
}

export function catColor(category: string): string {
  return CAT_COLORS[category] ?? '#71717a'
}
