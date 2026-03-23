import { useState, useEffect } from 'react'

export default function ReplyModal({ email, isOpen, onClose }) {
  if (!isOpen || !email) {
    return null
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-lg max-w-2xl w-full max-h-96 overflow-y-auto">
        {/* Modal Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">Email Reply</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-6">
          {/* Customer Email */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">From:</h3>
            <p className="text-gray-900 break-all">{email.sender}</p>
          </div>

          {/* Subject */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Subject:</h3>
            <p className="text-gray-900">{email.subject}</p>
          </div>

          {/* Original Message */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Original Message:</h3>
            <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
              <p className="text-gray-700 whitespace-pre-wrap text-sm">{email.body}</p>
            </div>
          </div>

          {/* Generated Reply */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Generated Reply:</h3>
            <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
              <p className="text-gray-800 whitespace-pre-wrap text-sm font-medium">{email.reply}</p>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 p-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
