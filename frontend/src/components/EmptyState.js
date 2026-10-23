import React from 'react';
import { Link } from 'react-router-dom';

export default function EmptyState({ title = 'No records found', message = 'Get started by creating your first entry.', actionText, actionLink }) {
  return (
    <div className="text-center py-12 px-4 bg-white rounded-xl border border-dashed border-gray-300">
      <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <h3 className="mt-2 text-sm font-semibold text-gray-900">{title}</h3>
      <p className="mt-1 text-sm text-gray-500">{message}</p>
      {actionText && actionLink && (
        <div className="mt-5">
          <Link
            to={actionLink}
            className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition"
          >
            {actionText}
          </Link>
        </div>
      )}
    </div>
  );
}
