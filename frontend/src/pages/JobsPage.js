import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import JobTable from '../components/JobTable';
import EmptyState from '../components/EmptyState';

export default function JobsPage({ jobs, onCancelJob, onRetryJob, actionLoadingId }) {
  const [filter, setFilter] = useState('ALL');

  const filteredJobs = jobs.filter((job) => {
    if (filter === 'ACTIVE') return job.status === 'QUEUED' || job.status === 'PROCESSING';
    if (filter === 'COMPLETED') return job.status === 'COMPLETED';
    if (filter === 'FAILED') return job.status === 'FAILED';
    if (filter === 'CANCELLED') return job.status === 'CANCELLED';
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Processing Queue</h1>
          <p className="text-sm text-gray-500 mt-1">
            Real-time trace of scheduled operations, state transitions, and worker heartbeats
          </p>
        </div>
        <Link
          to="/upload"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm transition shadow-sm self-start sm:self-auto"
        >
          + New Job
        </Link>
      </div>

      {/* Filter Tabs */}
      <div className="flex border-b border-gray-200 gap-6 text-sm font-medium">
        {[
          { id: 'ALL', label: 'All Jobs', count: jobs.length },
          { id: 'ACTIVE', label: 'Active', count: jobs.filter((j) => j.status === 'QUEUED' || j.status === 'PROCESSING').length },
          { id: 'COMPLETED', label: 'Completed', count: jobs.filter((j) => j.status === 'COMPLETED').length },
          { id: 'FAILED', label: 'Failed', count: jobs.filter((j) => j.status === 'FAILED').length },
          { id: 'CANCELLED', label: 'Cancelled', count: jobs.filter((j) => j.status === 'CANCELLED').length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilter(tab.id)}
            className={`pb-3 font-semibold text-xs uppercase tracking-wider transition relative ${
              filter === tab.id
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-800'
            }`}
          >
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>

      {filteredJobs.length === 0 ? (
        <EmptyState
          title={`No ${filter.toLowerCase()} jobs found`}
          message="Jobs submitted to the queue will appear here with live WebSocket progress."
          actionText="Create a job"
          actionLink="/upload"
        />
      ) : (
        <JobTable
          jobs={filteredJobs}
          onCancel={onCancelJob}
          onRetry={onRetryJob}
          actionLoadingId={actionLoadingId}
        />
      )}
    </div>
  );
}
