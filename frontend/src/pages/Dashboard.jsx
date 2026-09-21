import { useEffect } from 'react'
import { Link } from 'react-router-dom'

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
  const { visibleEmails, loadingEmails, refreshEmails, issues, refreshIssues } = useData()

  useEffect(() => {
    refreshEmails()
    refreshIssues()
    const interval = setInterval(() => {
      refreshEmails()
      refreshIssues()
    }, 30000)
    return () => clearInterval(interval)
  }, [refreshEmails, refreshIssues])

  const replied = visibleEmails.filter((item) => item.status === 'replied').length
  const failed = visibleEmails.filter((item) => item.status === 'failed').length
  const openIssuesCount = (issues || []).filter((i) => i.status !== 'resolved').length
  const refundCount = (issues || []).filter((i) => i.status === 'refund_initiated').length

  return (
    <div className="space-y-6">
      {/* Top Stat Cards */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase text-slate-500 font-semibold tracking-wider">Total Emails</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">{visibleEmails.length}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase text-slate-500 font-semibold tracking-wider">Auto-Replied</p>
          <p className="mt-2 text-2xl font-bold text-emerald-700">{replied}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase text-slate-500 font-semibold tracking-wider">Active Disputes / Issues</p>
          <p className="mt-2 text-2xl font-bold text-amber-700">{openIssuesCount}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase text-slate-500 font-semibold tracking-wider">Refunds Initiated</p>
          <p className="mt-2 text-2xl font-bold text-indigo-700">{refundCount}</p>
        </div>
      </section>

      {/* Autonomous Defect Triage & Open Issues Preview */}
      {issues && issues.length > 0 && (
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Recent Defect Triage & Action Resolutions</h2>
              <p className="text-xs text-slate-500">Autonomous multimodal defect verification and action decisions</p>
            </div>
            <Link
              to="/issues"
              className="text-xs font-semibold text-slate-900 hover:text-slate-700 underline"
            >
              View All Issues ({issues.length}) →
            </Link>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            {issues.slice(0, 3).map((issue) => (
              <div
                key={issue.id}
                className="rounded-lg border border-slate-100 bg-slate-50/75 p-3.5 space-y-2 hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-slate-700">{issue.order_number || 'Order'}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      issue.status === 'refund_initiated'
                        ? 'bg-emerald-100 text-emerald-800'
                        : issue.status === 'exchange_pending'
                        ? 'bg-indigo-100 text-indigo-800'
                        : issue.status === 'resolved'
                        ? 'bg-slate-200 text-slate-700'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {issue.status.replace('_', ' ')}
                  </span>
                </div>
                <div className="font-semibold text-slate-900 text-xs truncate">{issue.issue_title}</div>
                <div className="text-xs text-slate-500 line-clamp-2">{issue.resolution_notes || issue.description}</div>
                {issue.defect_type && issue.defect_type !== 'none' && (
                  <div className="text-xs text-purple-700 font-medium">
                    Defect: {issue.defect_type.replace('_', ' ')} ({Math.round((Number(issue.defect_area_ratio) || 0) * 100)}% DAR)
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Main Email Table */}
      <div className="space-y-2">
        <h2 className="text-base font-bold text-slate-900">Inbound Customer Email Stream</h2>
        {loadingEmails ? <SkeletonRows /> : <EmailTable emails={visibleEmails} />}
      </div>
    </div>
  )
}
