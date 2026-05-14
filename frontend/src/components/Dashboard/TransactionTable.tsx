import { useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, ChevronsUpDown, Search } from 'lucide-react'
import clsx from 'clsx'
import { catColor } from '../../constants'
import { fmtCurrency } from '../../lib/format'
import type { Transaction } from '../../types'

const PAGE_SIZE = 25

type SortCol = 'date' | 'merchant' | 'amount' | 'category'
type SortDir = 'asc' | 'desc'

interface Props {
  transactions: Transaction[]
}

export function TransactionTable({ transactions }: Props) {
  const [query, setQuery] = useState('')
  const [activeCats, setActiveCats] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)
  const [sortCol, setSortCol] = useState<SortCol>('date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const categories = useMemo(
    () => [...new Set(transactions.map((t) => t.category!))].sort(),
    [transactions],
  )

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    transactions.forEach((t) => {
      counts[t.category!] = (counts[t.category!] ?? 0) + 1
    })
    return counts
  }, [transactions])

  const filtered = useMemo(() => {
    const q = query.toLowerCase()
    return transactions.filter((t) => {
      if (activeCats.size > 0 && !activeCats.has(t.category!)) return false
      if (q && !t.merchant.toLowerCase().includes(q) && !t.description.toLowerCase().includes(q))
        return false
      return true
    })
  }, [transactions, query, activeCats])

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let cmp = 0
      if (sortCol === 'date') cmp = a.date.localeCompare(b.date)
      else if (sortCol === 'merchant') cmp = a.merchant.localeCompare(b.merchant)
      else if (sortCol === 'amount') cmp = a.amount - b.amount
      else if (sortCol === 'category') cmp = (a.category ?? '').localeCompare(b.category ?? '')
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [filtered, sortCol, sortDir])

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const pageItems = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const filteredTotal = filtered.reduce((s, t) => s + t.amount, 0)

  function toggleSort(col: SortCol) {
    if (sortCol === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortCol(col)
      setSortDir(col === 'amount' ? 'desc' : 'asc')
    }
    setPage(1)
  }

  function toggleCat(cat: string) {
    setActiveCats((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
    setPage(1)
  }

  function handleSearch(value: string) {
    setQuery(value)
    setPage(1)
  }

  const columns: { label: string; col?: SortCol; right?: boolean }[] = [
    { label: 'Date', col: 'date' },
    { label: 'Merchant', col: 'merchant' },
    { label: 'Description' },
    { label: 'Category', col: 'category' },
    { label: 'Amount', col: 'amount', right: true },
  ]

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative shrink-0 sm:w-72">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search merchant or description…"
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900 py-2 pl-9 pr-3 text-sm placeholder:text-zinc-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/40 transition-colors"
          />
        </div>
        <div className="flex gap-1.5 overflow-x-auto pb-0.5">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => toggleCat(cat)}
              className={clsx(
                'flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors',
                activeCats.has(cat)
                  ? 'bg-zinc-700 text-zinc-100'
                  : 'bg-zinc-800/60 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300',
              )}
            >
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: catColor(cat) }}
              />
              {cat}
              <span className={clsx('tabular-nums', activeCats.has(cat) ? 'text-zinc-400' : 'text-zinc-600')}>
                {categoryCounts[cat]}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-zinc-800">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900">
                {columns.map(({ label, col, right }) => (
                  <th
                    key={label}
                    onClick={col ? () => toggleSort(col) : undefined}
                    className={clsx(
                      'px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-zinc-500',
                      right ? 'text-right' : 'text-left',
                      col && 'cursor-pointer select-none hover:text-zinc-300 transition-colors',
                    )}
                  >
                    {label}
                    {col && (
                      sortCol === col
                        ? (sortDir === 'asc'
                          ? <ChevronUp className="ml-1 inline-block h-3 w-3" />
                          : <ChevronDown className="ml-1 inline-block h-3 w-3" />)
                        : <ChevronsUpDown className="ml-1 inline-block h-3 w-3 opacity-30" />
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageItems.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-sm text-zinc-600">
                    No transactions match your filters.
                  </td>
                </tr>
              ) : (
                pageItems.map((tx, i) => (
                  <tr
                    key={i}
                    className="border-b border-zinc-800/50 transition-colors hover:bg-zinc-900/40"
                  >
                    <td className="px-4 py-3 tabular-nums text-zinc-400">{tx.date}</td>
                    <td className="px-4 py-3 font-medium">{tx.merchant}</td>
                    <td className="max-w-[220px] truncate px-4 py-3 text-zinc-400">
                      {tx.description}
                    </td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5">
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ background: catColor(tx.category!) }}
                        />
                        <span className="text-zinc-300">{tx.category}</span>
                      </span>
                    </td>
                    <td
                      className={clsx(
                        'px-4 py-3 text-right tabular-nums',
                        tx.amount < 0 && 'text-emerald-400',
                      )}
                    >
                      {fmtCurrency(tx.amount)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Table footer */}
        <div className="flex items-center justify-between border-t border-zinc-800 bg-zinc-900/50 px-4 py-2.5">
          <p className="text-xs text-zinc-500">
            {filtered.length.toLocaleString()} of {transactions.length.toLocaleString()}{' '}
            transactions
            {filtered.length > 0 && (
              <span className="text-zinc-600"> · {fmtCurrency(filteredTotal)} total</span>
            )}
          </p>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded px-2 py-1 text-xs text-zinc-500 transition-colors hover:text-zinc-300 disabled:opacity-30"
              >
                ←
              </button>
              <span className="text-xs text-zinc-500">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="rounded px-2 py-1 text-xs text-zinc-500 transition-colors hover:text-zinc-300 disabled:opacity-30"
              >
                →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
