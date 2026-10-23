import React from 'react';
import { Link } from 'react-router-dom';

export default function Navbar({ user, onLogout }) {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2 font-bold text-xl text-gray-900 tracking-tight">
              <span className="h-8 w-8 rounded-lg bg-blue-600 text-white flex items-center justify-center font-black text-lg">
                F
              </span>
              <span>FileFlow</span>
            </Link>
            <span className="hidden sm:inline-block px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
              Distributed Cloud
            </span>
          </div>

          <div className="flex items-center gap-4">
            {user ? (
              <>
                <div className="hidden sm:flex flex-col text-right">
                  <span className="text-xs font-semibold text-gray-900">{user.email}</span>
                  <span className="text-[10px] text-emerald-600 font-medium">● Connected</span>
                </div>
                <button
                  onClick={onLogout}
                  className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50 transition"
                >
                  Logout
                </button>
              </>
            ) : (
              <div className="flex items-center gap-3">
                <Link to="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900">
                  Login
                </Link>
                <Link
                  to="/register"
                  className="px-3.5 py-1.5 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 transition"
                >
                  Register
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
