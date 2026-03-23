import { useState, useEffect } from 'react'
import axios from 'axios'
import Navbar from '../components/Navbar'
import EmailTable from '../components/EmailTable'
import ReplyModal from '../components/ReplyModal'

const API_BASE_URL = 'http://localhost:8000'

export default function Dashboard() {
  const [emails, setEmails] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedEmail, setSelectedEmail] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Fetch emails from API
  const fetchEmails = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await axios.get(`${API_BASE_URL}/api/emails`, {
        params: { limit: 100 }
      })

      if (response.data && response.data.emails) {
        setEmails(response.data.emails)
      }
    } catch (err) {
      console.error('Failed to fetch emails:', err)
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Failed to load emails. Make sure the backend is running on http://localhost:8000'
      )
    } finally {
      setLoading(false)
    }
  }

  // Fetch emails on component mount
  useEffect(() => {
    fetchEmails()
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchEmails, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleViewReply = (email) => {
    setSelectedEmail(email)
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setSelectedEmail(null)
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      {/* Navbar */}
      <Navbar
        totalEmails={emails.length}
        onRefresh={fetchEmails}
        isLoading={loading}
      />

      {/* Main Content */}
      <main className="flex-1 p-6 overflow-auto">
        <div className="max-w-7xl mx-auto">
          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl">
              <h3 className="text-sm font-semibold text-red-900 mb-1">Error</h3>
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Loading State */}
          {loading && emails.length === 0 && (
            <div className="text-center py-12">
              <div className="inline-block">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
                <p className="text-gray-600 font-medium">Loading emails...</p>
              </div>
            </div>
          )}

          {/* Email Table */}
          {!loading && (
            <EmailTable
              emails={emails}
              onViewReply={handleViewReply}
            />
          )}

          {/* No Data State */}
          {!loading && !error && emails.length === 0 && (
            <div className="bg-white rounded-xl shadow-sm p-12 text-center">
              <svg
                className="w-16 h-16 text-gray-300 mx-auto mb-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                />
              </svg>
              <h3 className="text-gray-700 font-semibold text-lg mb-2">No emails yet</h3>
              <p className="text-gray-500">Incoming emails will appear here once processed by the system.</p>
            </div>
          )}
        </div>
      </main>

      {/* Reply Modal */}
      <ReplyModal
        email={selectedEmail}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  )
}
