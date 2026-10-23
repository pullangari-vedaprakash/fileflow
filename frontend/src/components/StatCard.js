import React from 'react';

export default function StatCard({ label, value, icon, color = 'text-blue-600', trend }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200/80 p-5 shadow-sm hover:shadow transition-shadow">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{label}</span>
        {icon && <span className={`p-2 rounded-lg bg-gray-50 ${color}`}>{icon}</span>}
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-3xl font-extrabold text-gray-900 tracking-tight">{value}</span>
        {trend && <span className="text-xs font-medium text-gray-500">{trend}</span>}
      </div>
    </div>
  );
}
