import { useEffect } from 'react'

import Charts from '../components/Charts'
import { useData } from '../context/DataContext'

export default function AnalyticsPage() {
  const { visibleEmails, refreshEmails, refreshAnalytics } = useData()

  useEffect(() => {
    refreshEmails()
    refreshAnalytics()
  }, [refreshEmails, refreshAnalytics])

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-slate-900">Analytics</h2>
      <Charts emails={visibleEmails} />
    </div>
  )
}
