import { useRef, useState } from 'react'
import { getDashboard, streamCategorize, uploadCSV } from './api'
import { Sidebar } from './components/Sidebar'
import { Landing } from './components/Landing'
import { Preview } from './components/Preview'
import { Dashboard } from './components/Dashboard'
import type { AppView, DashboardData, UploadResponse } from './types'

export default function App() {
  const [view, setView] = useState<AppView>('landing')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<UploadResponse | null>(null)
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [isCategorizing, setIsCategorizing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const esRef = useRef<EventSource | null>(null)

  async function handleUpload(file: File) {
    setError(null)
    setDashboardData(null)
    setProgress(null)
    try {
      const data = await uploadCSV(file)
      setSessionId(data.session_id)
      setPreviewData(data)
      setView('preview')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  function handleCategorize() {
    if (!sessionId || !apiKey || isCategorizing) return
    esRef.current?.close()
    setIsCategorizing(true)
    setProgress(null)
    setError(null)

    esRef.current = streamCategorize(sessionId, apiKey, {
      onProgress: (done, total) => setProgress({ done, total }),
      onDone: async () => {
        try {
          const data = await getDashboard(sessionId!)
          setDashboardData(data)
          setView('dashboard')
        } catch (e) {
          setError((e as Error).message)
        } finally {
          setIsCategorizing(false)
          setProgress(null)
        }
      },
      onError: (msg) => {
        setError(msg)
        setIsCategorizing(false)
      },
    })
  }

  function handleReset() {
    esRef.current?.close()
    setView('landing')
    setSessionId(null)
    setPreviewData(null)
    setDashboardData(null)
    setApiKey('')
    setProgress(null)
    setIsCategorizing(false)
    setError(null)
  }

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-50">
      <Sidebar
        hasData={view !== 'landing'}
        apiKey={apiKey}
        onApiKeyChange={setApiKey}
        onUpload={handleUpload}
        onCategorize={handleCategorize}
        onReset={handleReset}
        canCategorize={view !== 'landing' && !!apiKey && !isCategorizing}
        isCategorizing={isCategorizing}
        progress={progress}
        error={error}
      />
      <main className="flex-1 overflow-y-auto">
        {view === 'landing' && <Landing />}
        {view === 'preview' && previewData && <Preview data={previewData} />}
        {view === 'dashboard' && dashboardData && <Dashboard data={dashboardData} />}
      </main>
    </div>
  )
}
