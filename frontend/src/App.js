import React, { useState, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import axios from 'axios';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';
const WS_BASE = API.replace(/^http/, 'ws').replace(/\/api$/, '');

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(null);

  useEffect(() => {
    if (token) {
      axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then(res => setUser(res.data))
        .catch(() => { localStorage.removeItem('token'); setToken(null); });
    }
  }, [token]);

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white shadow px-6 py-4 flex justify-between items-center">
          <Link to="/" className="text-xl font-bold text-blue-600">FileFlow</Link>
          {token && (
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">{user?.email}</span>
              <button onClick={logout} className="text-red-500 text-sm">Logout</button>
            </div>
          )}
        </nav>
        <div className="max-w-6xl mx-auto p-6">
          <Routes>
            <Route path="/login" element={<Login setToken={setToken} />} />
            <Route path="/register" element={<Register setToken={setToken} />} />
            <Route path="/" element={token ? <Dashboard token={token} user={user} /> : <Navigate to="/login" />} />
            <Route path="/upload" element={token ? <Upload token={token} /> : <Navigate to="/login" />} />
            <Route path="/jobs" element={token ? <Jobs token={token} user={user} /> : <Navigate to="/login" />} />
            <Route path="/jobs/:id" element={token ? <JobDetail token={token} /> : <Navigate to="/login" />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

function Login({ setToken }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post(`${API}/auth/login`, { email, password });
      localStorage.setItem('token', res.data.access_token);
      setToken(res.data.access_token);
    } catch {
      setError('Invalid credentials');
    }
  };

  return (
    <div className="max-w-md mx-auto mt-16 p-8 bg-white rounded-lg shadow">
      <h2 className="text-2xl font-semibold mb-6">Login</h2>
      {error && <p className="text-red-500 mb-4">{error}</p>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} className="w-full p-3 border rounded" required />
        <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} className="w-full p-3 border rounded" required />
        <button type="submit" className="w-full bg-blue-600 text-white p-3 rounded hover:bg-blue-700">Login</button>
      </form>
      <p className="mt-4 text-center text-sm">No account? <Link to="/register" className="text-blue-600">Register</Link></p>
    </div>
  );
}

function Register({ setToken }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post(`${API}/auth/register`, { email, password });
      localStorage.setItem('token', res.data.access_token);
      setToken(res.data.access_token);
    } catch {
      alert('Registration failed (email may already exist)');
    }
  };

  return (
    <div className="max-w-md mx-auto mt-16 p-8 bg-white rounded-lg shadow">
      <h2 className="text-2xl font-semibold mb-6">Register</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} className="w-full p-3 border rounded" required />
        <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} className="w-full p-3 border rounded" required />
        <button type="submit" className="w-full bg-green-600 text-white p-3 rounded hover:bg-green-700">Create Account</button>
      </form>
      <p className="mt-4 text-center text-sm"><Link to="/login" className="text-blue-600">Back to Login</Link></p>
    </div>
  );
}

function Dashboard({ token, user }) {
  const [stats, setStats] = useState({ files: 0, active: 0, completed: 0, failed: 0 });

  useEffect(() => {
    const headers = { Authorization: `Bearer ${token}` };
    Promise.all([
      axios.get(`${API}/files/`, { headers }),
      axios.get(`${API}/jobs/`, { headers }),
    ]).then(([filesRes, jobsRes]) => {
      const jobs = jobsRes.data;
      setStats({
        files: filesRes.data.length,
        active: jobs.filter(j => j.status === 'QUEUED' || j.status === 'PROCESSING').length,
        completed: jobs.filter(j => j.status === 'COMPLETED').length,
        failed: jobs.filter(j => j.status === 'FAILED').length,
      });
    });
  }, [token]);

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Files" value={stats.files} />
        <StatCard label="Active Jobs" value={stats.active} color="text-blue-600" />
        <StatCard label="Completed" value={stats.completed} color="text-green-600" />
        <StatCard label="Failed" value={stats.failed} color="text-red-600" />
      </div>
      <div className="flex gap-4">
        <Link to="/upload" className="bg-blue-600 text-white px-6 py-3 rounded hover:bg-blue-700">Upload File</Link>
        <Link to="/jobs" className="bg-gray-800 text-white px-6 py-3 rounded hover:bg-gray-900">View Jobs</Link>
      </div>
    </div>
  );
}

function StatCard({ label, value, color = "text-gray-800" }) {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-sm text-gray-500 mt-1">{label}</div>
    </div>
  );
}

function Upload({ token }) {
  const [file, setFile] = useState(null);
  const [operations, setOperations] = useState([]);
  const [priority, setPriority] = useState('NORMAL');
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');

  const imageOps = ['resize', 'compress', 'thumbnail'];
  const pdfOps = ['extract_text', 'generate_preview'];

  const toggleOp = (op) => {
    setOperations(prev => prev.includes(op) ? prev.filter(o => o !== op) : [...prev, op]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || operations.length === 0) return;
    setUploading(true);
    setMessage('');
    try {
      const form = new FormData();
      form.append('file', file);
      const uploadRes = await axios.post(`${API}/files/upload`, form, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
      });
      await axios.post(`${API}/jobs/`, {
        file_id: uploadRes.data.id,
        operations,
        priority,
      }, { headers: { Authorization: `Bearer ${token}` } });
      setMessage('Job created successfully!');
      setFile(null);
      setOperations([]);
    } catch (err) {
      setMessage('Error: ' + (err.response?.data?.detail || err.message));
    }
    setUploading(false);
  };

  const isImage = file && file.type.startsWith('image/');
  const isPdf = file && file.type === 'application/pdf';

  return (
    <div className="max-w-lg">
      <h1 className="text-3xl font-bold mb-6">Upload & Process</h1>
      <form onSubmit={handleSubmit} className="bg-white p-6 rounded-lg shadow space-y-4">
        <input type="file" accept=".jpg,.jpeg,.png,.pdf,.webp" onChange={e => setFile(e.target.files[0])} className="w-full" />
        {(isImage || isPdf) && (
          <div>
            <p className="font-medium mb-2">Operations</p>
            <div className="space-y-1">
              {(isImage ? imageOps : pdfOps).map(op => (
                <label key={op} className="flex items-center gap-2">
                  <input type="checkbox" checked={operations.includes(op)} onChange={() => toggleOp(op)} />
                  {op}
                </label>
              ))}
            </div>
          </div>
        )}
        <div>
          <p className="font-medium mb-2">Priority</p>
          <select value={priority} onChange={e => setPriority(e.target.value)} className="w-full p-2 border rounded">
            <option value="HIGH">High</option>
            <option value="NORMAL">Normal</option>
            <option value="LOW">Low</option>
          </select>
        </div>
        <button type="submit" disabled={uploading || !file || operations.length === 0} className="w-full bg-blue-600 text-white p-3 rounded disabled:opacity-50">
          {uploading ? 'Creating...' : 'Create Job'}
        </button>
        {message && <p className={message.startsWith('Error') ? 'text-red-500' : 'text-green-600'}>{message}</p>}
      </form>
    </div>
  );
}

function Jobs({ token, user }) {
  const [jobs, setJobs] = useState([]);
  const wsRef = useRef(null);

  const fetchJobs = async () => {
    const res = await axios.get(`${API}/jobs/`, { headers: { Authorization: `Bearer ${token}` } });
    setJobs(res.data);
  };

  useEffect(() => {
    fetchJobs();
    if (user?.id) {
      const ws = new WebSocket(`${WS_BASE}/ws/${user.id}`);
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'job_update') {
          setJobs(prev => prev.map(j => j.id === data.job_id ? { ...j, status: data.status, progress: data.progress ?? j.progress, error_message: data.error } : j));
        }
      };
      wsRef.current = ws;
      return () => ws.close();
    }
  }, [token, user]);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Jobs</h1>
        <Link to="/upload" className="bg-blue-600 text-white px-4 py-2 rounded">New Job</Link>
      </div>
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-3 text-left">ID</th>
              <th className="p-3 text-left">Status</th>
              <th className="p-3 text-left">Progress</th>
              <th className="p-3 text-left">Priority</th>
              <th className="p-3 text-left">Created</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map(job => (
              <tr key={job.id} className="border-t">
                <td className="p-3">{job.id}</td>
                <td className="p-3"><StatusBadge status={job.status} /></td>
                <td className="p-3">{job.progress?.toFixed(0) || 0}%</td>
                <td className="p-3">{job.priority}</td>
                <td className="p-3">{new Date(job.created_at).toLocaleString()}</td>
                <td className="p-3"><Link to={`/jobs/${job.id}`} className="text-blue-600">Details</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
        {jobs.length === 0 && <p className="p-6 text-center text-gray-500">No jobs yet</p>}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const colors = {
    QUEUED: 'bg-yellow-100 text-yellow-800',
    PROCESSING: 'bg-blue-100 text-blue-800',
    COMPLETED: 'bg-green-100 text-green-800',
    FAILED: 'bg-red-100 text-red-800',
    CANCELLED: 'bg-gray-100 text-gray-800',
  };
  return <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status] || ''}`}>{status}</span>;
}

function JobDetail({ token }) {
  const [job, setJob] = useState(null);
  const [results, setResults] = useState([]);
  const id = window.location.pathname.split('/').pop();

  useEffect(() => {
    const headers = { Authorization: `Bearer ${token}` };
    axios.get(`${API}/jobs/${id}`, { headers }).then(res => setJob(res.data));
    axios.get(`${API}/jobs/${id}/results`, { headers }).then(res => setResults(res.data)).catch(() => {});
  }, [id, token]);

  if (!job) return <p>Loading...</p>;

  return (
    <div>
      <h1 className="text-3xl font-bold mb-4">Job #{job.id}</h1>
      <div className="bg-white p-6 rounded-lg shadow mb-6">
        <p><strong>Status:</strong> <StatusBadge status={job.status} /></p>
        <p className="mt-2"><strong>Progress:</strong> {job.progress?.toFixed(0)}%</p>
        <p className="mt-2"><strong>Priority:</strong> {job.priority}</p>
        <p className="mt-2"><strong>Operations:</strong> {job.operations?.join(', ')}</p>
        {job.error_message && <p className="mt-2 text-red-600"><strong>Error:</strong> {job.error_message}</p>}
      </div>
      {results.length > 0 && (
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Results</h2>
          <div className="space-y-2">
            {results.map(r => (
              <div key={r.id} className="flex justify-between items-center">
                <span>{r.file_name || r.type}</span>
                {r.download_url && (
                  <a href={r.download_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">Download</a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
