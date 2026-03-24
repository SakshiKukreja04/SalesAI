import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ALLOWED_INTENTS } from '../constants/intents'

const chartColors = ['#1d4ed8', '#0f766e', '#b45309', '#be123c', '#4f46e5', '#047857']

const groupByIntent = (emails) =>
  ALLOWED_INTENTS.map((intent) => ({
    name: intent,
    value: emails.filter((item) => item.intent === intent).length,
  }))

const groupByStatus = (emails) => {
  const statusCount = emails.reduce(
    (acc, item) => {
      const status = (item.status || 'unknown').toLowerCase()
      if (!acc[status]) {
        acc[status] = 0
      }
      acc[status] += 1
      return acc
    },
    { replied: 0, failed: 0, escalated: 0 },
  )

  return Object.entries(statusCount).map(([name, value]) => ({ name, value }))
}

const groupByTime = (emails) => {
  const buckets = {}
  emails.forEach((item) => {
    const raw = item.timestamp || item.created_at
    const date = raw ? new Date(raw) : null
    if (!date || Number.isNaN(date.getTime())) {
      return
    }
    const key = date.toISOString().slice(0, 10)
    buckets[key] = (buckets[key] || 0) + 1
  })

  return Object.keys(buckets)
    .sort()
    .map((key) => ({ date: key, value: buckets[key] }))
}

const groupByEmotion = (emails) => {
  const count = emails.reduce((acc, item) => {
    const emotion = item.emotion || 'unknown'
    acc[emotion] = (acc[emotion] || 0) + 1
    return acc
  }, {})

  return Object.entries(count).map(([name, value]) => ({ name, value }))
}

function Card({ title, children }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>
      <div className="h-72">{children}</div>
    </div>
  )
}

export default function Charts({ emails = [] }) {
  const intentData = groupByIntent(emails)
  const statusData = groupByStatus(emails)
  const timelineData = groupByTime(emails)
  const emotionData = groupByEmotion(emails)

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Card title="Emails per Intent">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={intentData} margin={{ top: 10, right: 10, left: 0, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" angle={-20} textAnchor="end" interval={0} height={70} />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill="#0f766e" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Intent Distribution">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={intentData} dataKey="value" nameKey="name" outerRadius={100} label>
              {intentData.map((entry, index) => (
                <Cell key={entry.name} fill={chartColors[index % chartColors.length]} />
              ))}
            </Pie>
            <Legend />
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Emails Over Time">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={timelineData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#1d4ed8" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Response Status">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={statusData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill="#4f46e5" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Emotion Distribution">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={emotionData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill="#be123c" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  )
}
