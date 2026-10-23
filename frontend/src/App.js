import React, { useState, useEffect, useRef, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import api, { WS_URL } from './api';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import JobsPage from './pages/JobsPage';
import JobDetailPage from './pages/JobDetailPage';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const wsRef = useRef(null);

  // Fetch current user details
  useEffect(() => {
    if (token) {
      api.get('/auth/me')
        .then((res) => setUser(res.data))
        .catch(() => {
          localStorage.removeItem('token');
          setToken(null);
          setUser(null);
        });
    }
  }, [token]);

  // Fetch initial job list
  const fetchJobs = useCallback(async () => {
    if (!token) return;
    try {
      const res = await api.get('/jobs/');
      setJobs(res.data);
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchJobs();
    }
  }, [token, fetchJobs]);

  // Real-time WebSocket connection
  useEffect(() => {
    if (!user?.id) return;

    const wsUrl = `${WS_URL}/ws/${user.id}`;
    let ws;
    let reconnectTimer;

    const connect = () => {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('[WebSocket] Connected for live job progress updates');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'job_update') {
            setJobs((prev) =>
              prev.map((j) =>
                j.id === data.job_id
                  ? {
                      ...j,
                      status: data.status,
                      progress: data.progress != null ? data.progress : j.progress,
                      error_message: data.error != null ? data.error : j.error_message,
                    }
                  : j
              )
            );
          }
        } catch (err) {
          console.error('[WebSocket] Parse error:', err);
        }
      };

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected. Reconnecting in 3s...');
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error('[WebSocket] Error:', err);
        ws.close();
      };

      wsRef.current = ws;
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, [user?.id]);

  const handleLoginSuccess = (newToken) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    setJobs([]);
    if (wsRef.current) {
      wsRef.current.close();
    }
  };

  const handleCancelJob = async (jobId) => {
    setActionLoadingId(jobId);
    try {
      await api.post(`/jobs/${jobId}/cancel`);
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, status: 'CANCELLED' } : j))
      );
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to cancel job');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleRetryJob = async (jobId) => {
    setActionLoadingId(jobId);
    try {
      const res = await api.post(`/jobs/${jobId}/retry`);
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId
            ? { ...j, status: 'QUEUED', retry_count: res.data.retry_count, progress: 0 }
            : j
        )
      );
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to retry job');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleJobCreated = (newJob) => {
    setJobs((prev) => [newJob, ...prev]);
  };

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-gray-900">
        <Navbar user={user} onLogout={handleLogout} />

        <div className="flex flex-1">
          {token && <Sidebar />}

          <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
            <Routes>
              <Route
                path="/login"
                element={
                  !token ? (
                    <LoginPage onLoginSuccess={handleLoginSuccess} />
                  ) : (
                    <Navigate to="/" replace />
                  )
                }
              />
              <Route
                path="/register"
                element={
                  !token ? (
                    <RegisterPage onLoginSuccess={handleLoginSuccess} />
                  ) : (
                    <Navigate to="/" replace />
                  )
                }
              />
              <Route
                path="/"
                element={
                  token ? (
                    <DashboardPage
                      jobs={jobs}
                      onCancelJob={handleCancelJob}
                      onRetryJob={handleRetryJob}
                      actionLoadingId={actionLoadingId}
                    />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/upload"
                element={
                  token ? (
                    <UploadPage onJobCreated={handleJobCreated} />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/jobs"
                element={
                  token ? (
                    <JobsPage
                      jobs={jobs}
                      onCancelJob={handleCancelJob}
                      onRetryJob={handleRetryJob}
                      actionLoadingId={actionLoadingId}
                    />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/jobs/:id"
                element={
                  token ? (
                    <JobDetailPage
                      jobs={jobs}
                      onCancelJob={handleCancelJob}
                      onRetryJob={handleRetryJob}
                      actionLoadingId={actionLoadingId}
                    />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
