export function Landing() {
  return (
    <div className="flex h-full min-h-screen items-center justify-center">
      <div className="text-center">
        <div className="mb-5 text-6xl leading-none opacity-10 select-none">●</div>
        <h1 className="mb-2 text-xl font-semibold tracking-tight">Budget Tracker</h1>
        <p className="max-w-xs text-sm leading-relaxed text-zinc-500">
          Upload a transaction CSV, enter your DeepSeek API key, and click{' '}
          <span className="text-zinc-300">Categorize</span>.
        </p>
        <p className="mt-3 text-xs text-zinc-700">Robinhood · Capital One</p>
      </div>
    </div>
  )
}
