export function fmtDollar(v: number): string {
  return v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

export function fmtCurrency(v: number): string {
  return v.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export function fmtMonthLabel(ym: string): string {
  // ym is "YYYY-MM" — render as "Jan", "Feb", etc.
  const [year, month] = ym.split('-').map(Number)
  return new Date(year, month - 1, 1).toLocaleString('en-US', { month: 'short' })
}
