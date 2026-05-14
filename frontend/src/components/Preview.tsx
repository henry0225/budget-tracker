import { fmtCurrency } from '../lib/format'
import type { UploadResponse } from '../types'

interface Props {
  data: UploadResponse
}

export function Preview({ data }: Props) {
  const remaining = data.transaction_count - data.preview.length
  const showDescription = data.preview.some((tx) => tx.description !== tx.merchant)

  const parts: string[] = []
  if (data.cc_count > 0) parts.push(`${data.cc_count.toLocaleString()} card purchases`)
  if (data.p2p_count > 0) parts.push(`${data.p2p_count.toLocaleString()} Venmo/Zelle sent`)

  return (
    <div className="p-8">
      <h2 className="text-lg font-semibold tracking-tight">Transaction Preview</h2>
      <p className="mt-1 text-sm text-zinc-500">
        {parts.length ? parts.join(' · ') : `${data.transaction_count.toLocaleString()} transactions`}
        {' '}· {data.merchant_count} unique merchants
      </p>

      <div className="mt-6 overflow-hidden rounded-xl border border-zinc-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900">
              {['Date', 'Merchant', ...(showDescription ? ['Description'] : []), 'Amount'].map(
                (h) => (
                  <th
                    key={h}
                    className={`px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-zinc-500 ${
                      h === 'Amount' ? 'text-right' : 'text-left'
                    }`}
                  >
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {data.preview.map((tx, i) => (
              <tr
                key={i}
                className="border-b border-zinc-800/60 transition-colors hover:bg-zinc-900/40"
              >
                <td className="px-4 py-3 tabular-nums text-zinc-400">{tx.date}</td>
                <td className="px-4 py-3 font-medium">{tx.merchant}</td>
                {showDescription && (
                  <td className="max-w-xs truncate px-4 py-3 text-zinc-400">{tx.description}</td>
                )}
                <td className="px-4 py-3 text-right tabular-nums">{fmtCurrency(tx.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {remaining > 0 && (
          <div className="border-t border-zinc-800 bg-zinc-900/50 px-4 py-2.5">
            <p className="text-xs text-zinc-600">+ {remaining.toLocaleString()} more transactions</p>
          </div>
        )}
      </div>

      <p className="mt-4 text-xs text-zinc-600">
        Enter your DeepSeek API key in the sidebar and click Categorize to continue.
      </p>
    </div>
  )
}
