import { useEffect } from 'react'

import EmailTable from '../components/EmailTable'
import { useData } from '../context/DataContext'

function SkeletonRows() {
  return (
    <div className="space-y-3">
      {[...Array(4)].map((_, idx) => (
        <div key={idx} className="h-12 animate-pulse rounded-lg bg-slate-200" />
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { visibleEmails, loadingEmails, refreshEmails } = useData()

  useEffect(() => {
    refreshEmails()
    const interval = setInterval(refreshEmails, 30000)
    return () => clearInterval(interval)
  }, [refreshEmails])

  const replied = visibleEmails.filter((item) => item.status === 'replied').length
  const failed = visibleEmails.filter((item) => item.status === 'failed').length

  return (
    <div className="space-y-5">
      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Total Emails</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900">{visibleEmails.length}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Replied</p>
          <p className="mt-2 text-2xl font-semibold text-emerald-700">{replied}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Failed</p>
          <p className="mt-2 text-2xl font-semibold text-rose-700">{failed}</p>
        </div>
      </section>

      {loadingEmails ? <SkeletonRows /> : <EmailTable emails={visibleEmails} />}
    </div>
  )
}
