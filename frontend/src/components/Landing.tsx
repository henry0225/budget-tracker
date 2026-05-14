export function Landing() {
  return (
    <div className="flex h-full min-h-screen items-center justify-center">
      <div className="text-center">
        <div className="mb-5 text-6xl leading-none opacity-10 select-none">●</div>
        <h1 className="mb-2 text-xl font-semibold tracking-tight">Budget Tracker</h1>
        <p className="max-w-sm text-sm leading-relaxed text-zinc-500">
          Drop a credit-card CSV for AI-categorized spending, and/or a checking CSV to
          pull your <span className="text-zinc-300">Venmo &amp; Zelle</span> activity
          into the same dashboard.
        </p>
        <p className="mt-4 text-xs text-zinc-700">
          Robinhood · Capital One · 360 Checking
        </p>
      </div>
    </div>
  )
}
