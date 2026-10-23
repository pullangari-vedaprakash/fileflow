import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';
import StatCard from '../components/StatCard';
import JobTable from '../components/JobTable';
import EmptyState from '../components/EmptyState';
import LoadingState from '../components/LoadingState';

export default function DashboardPage({ jobs, onCancelJob, onRetryJob, actionLoadingId }) {
  const [fileCount, setFileCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/files/')
      .then((res) => setFileCount(res.data.length))
      .catch((err) => console.error('Failed to fetch files:', err))
      .finally(() => setLoading(false));
  }, []);

  const activeCount = jobs.filter((j) => j.status === 'QUEUED' || j.status === 'PROCESSING').length;
  const completedCount = jobs.filter((j) => j.status === 'COMPLETED').length;
  const failedCount = jobs.filter((j) => j.status === 'FAILED').length;

  const recentJobs = jobs.slice(0, 5);

  if (loading && jobs.length === 0) {
    return <LoadingState message="Loading platform metrics..." />;
  }

  return (
    <div className="space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">System Overview</h1>
          <p className="text-sm text-gray-500 mt-1">
            Real-time status of distributed asynchronous file processing pipeline
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm transition shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            Create Processing Job
          </Link>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        <StatCard
          label="Total Files"
          value={fileCount}
          color="text-indigo-600"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
          }
        />
        <StatCard
          label="Active In Queue"
          value={activeCount}
          color="text-blue-600"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
        />
        <StatCard
          label="Completed"
          value={completedCount}
          color="text-emerald-600"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
        <StatCard
          label="Failed"
          value={failedCount}
          color="text-rose-600"
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          }
        />
      </div>

      {/* Recent Jobs Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Recent Queue Activity</h2>
          {jobs.length > 5 && (
            <Link to="/jobs" className="text-sm font-semibold text-blue-600 hover:text-blue-800">
              View all ({jobs.length}) →
            </Link>
          )}
        </div>

        {recentJobs.length === 0 ? (
          <EmptyState
            title="Queue is empty"
            message="No asynchronous jobs have been processed yet."
            actionText="Upload a file to begin"
            actionLink="/upload"
          />
        ) : (
          <JobTable
            jobs={recentJobs}
            onCancel={onCancelJob}
            onRetry={onRetryJob}
            actionLoadingId={actionLoadingId}
          />
        )}
      </div>
    </div>
  );
}
