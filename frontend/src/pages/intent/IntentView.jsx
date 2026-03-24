import { useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'

import EmailTable from '../../components/EmailTable'
import { useAuth } from '../../context/AuthContext'
import { useData } from '../../context/DataContext'

export default function IntentView() {
  const { intent } = useParams()
  const intentName = decodeURIComponent(intent || '')
  const { isAdmin, profile } = useAuth()
  const { visibleEmails, refreshEmails } = useData()

  useEffect(() => {
    refreshEmails()
  }, [refreshEmails])

  const canAccess = isAdmin || (profile.assignedIntents || []).includes(intentName)

  const intentEmails = useMemo(
    () => visibleEmails.filter((item) => item.intent === intentName),
    [visibleEmails, intentName],
  )

  if (!canAccess) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-rose-700">
        You are not allowed to access this intent dashboard.
      </div>
    )
  }

  const replied = intentEmails.filter((item) => item.status === 'replied').length
  const failed = intentEmails.filter((item) => item.status === 'failed').length

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Intent</p>
          <p className="mt-2 text-lg font-semibold text-slate-900">{intentName}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Replied</p>
          <p className="mt-2 text-lg font-semibold text-emerald-700">{replied}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase text-slate-500">Failed</p>
          <p className="mt-2 text-lg font-semibold text-rose-700">{failed}</p>
        </div>
      </div>

      <EmailTable emails={intentEmails} />
    </div>
  )
}
