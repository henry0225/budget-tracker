import { useState } from 'react'
import { Download } from 'lucide-react'
import { catColor } from '../../constants'
import { fmtDollar } from '../../lib/format'
import type { DashboardData, Transaction } from '../../types'
import { Charts } from './Charts'
import { Insights } from './Insights'
import { TransactionTable } from './TransactionTable'

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: string
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5 transition-colors hover:border-zinc-700">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">{label}</p>
      <p
        className="mt-2.5 text-2xl font-semibold tracking-tight"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </p>
    </div>
  )
}

function exportCSV(transactions: Transaction[]) {
  const headers = ['Date', 'Merchant', 'Description', 'Amount', 'Category']
  const rows = transactions.map((t) => [
    t.date,
    `"${(t.merchant ?? '').replace(/"/g, '""')}"`,
    `"${(t.description ?? '').replace(/"/g, '""')}"`,
    t.amount.toFixed(2),
    t.category ?? '',
  ])
  const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'transactions.csv'
  a.click()
  URL.revokeObjectURL(url)
}

type Tab = 'transactions' | 'insights'

interface Props {
  data: DashboardData
}

export function Dashboard({ data }: Props) {
  const [tab, setTab] = useState<Tab>('transactions')
  const { metrics, category_totals, monthly_series, transactions, insights } = data

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-8">
      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard label="Total spending" value={fmtDollar(metrics.total)} />
        <MetricCard label="Transactions" value={metrics.count.toLocaleString()} />
        <MetricCard label="Avg transaction" value={fmtDollar(metrics.average)} />
        <MetricCard
          label="Top category"
          value={metrics.top_category}
          accent={catColor(metrics.top_category)}
        />
      </div>

      {/* Charts */}
      <Charts categoryTotals={category_totals} monthlySeries={monthly_series} />

      {/* Tabs */}
      <div>
        <div className="flex items-center justify-between border-b border-zinc-800">
          <div className="flex">
            {(['transactions', 'insights'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium capitalize transition-colors ${
                  tab === t
                    ? 'border-indigo-500 text-zinc-50'
                    : 'border-transparent text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <button
            onClick={() => exportCSV(transactions)}
            className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>
        <div className="mt-5">
          {tab === 'transactions' ? (
            <TransactionTable transactions={transactions} />
          ) : (
            <Insights insights={insights} />
          )}
        </div>
      </div>
    </div>
  )
}
