import React, { useMemo, useState, useEffect } from 'react';
import axios from 'axios';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  getFilteredRowModel,
  getSortedRowModel,
} from '@tanstack/react-table';
import { API_BASE_URL } from './config';

/**
 * Professional Flat Options Table
 * Designed exactly like the provided financial reference.
 */
const OptionsChain = ({ symbol }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [expiry, setExpiry] = useState('');
  const [optionType, setOptionType] = useState('All');
  const [moneyness, setMoneyness] = useState('All');
  const [volumeFilter, setVolumeFilter] = useState('All');
  const [strikeMin, setStrikeMin] = useState('');
  const [strikeMax, setStrikeMax] = useState('');

  // Fetch Data
  const fetchData = async (targetExpiry = '') => {
    setLoading(true);
    try {
      const token = localStorage.getItem('id_token');
      const url = targetExpiry
        ? `${API_BASE_URL}/stock-options/${symbol}?expiry=${targetExpiry}`
        : `${API_BASE_URL}/stock-options/${symbol}`;

      const response = await axios.get(url, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (response.data.success) {
        setData(response.data);
        if (!targetExpiry) setExpiry(response.data.selected_expiry);
      } else {
        setError(response.data.error || 'Failed to load options data');
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [symbol]);

  // Derived Data with Frontend Filtering
  const filteredData = useMemo(() => {
    if (!data || !data.data) return [];
    let list = [...data.data];

    // Filter by Option Type
    if (optionType !== 'All') {
      list = list.filter(item => item.type === optionType.toUpperCase());
    }

    // Filter by Moneyness (Simplified logic based on underlying value)
    const spot = list[0]?.underlying_value || 0;
    if (moneyness === 'ITM') {
      list = list.filter(item =>
        (item.type === 'CALL' && item.strike < spot) ||
        (item.type === 'PUT' && item.strike > spot)
      );
    } else if (moneyness === 'OTM') {
      list = list.filter(item =>
        (item.type === 'CALL' && item.strike > spot) ||
        (item.type === 'PUT' && item.strike < spot)
      );
    }

    // Filter by Volume
    if (volumeFilter === 'With Volume') {
      list = list.filter(item => (item.volume || 0) > 0);
    }

    // Filter by Strike Range
    if (strikeMin) list = list.filter(item => item.strike >= parseFloat(strikeMin));
    if (strikeMax) list = list.filter(item => item.strike <= parseFloat(strikeMax));

    return list;
  }, [data, optionType, moneyness, volumeFilter, strikeMin, strikeMax]);

  // Columns definition
  const columns = useMemo(() => [
    { accessorKey: 'expiry', header: 'EXPIRES' },
    { accessorKey: 'strike', header: 'STRIKE PRICE', cell: info => `₹${info.getValue().toLocaleString()}` },
    { accessorKey: 'last_price', header: 'CLOSE PRICE', cell: info => `₹${info.getValue()?.toFixed(2) || '0.00'}` },
    { accessorKey: 'type', header: 'PUT/CALL', cell: info => info.getValue().charAt(0) + info.getValue().slice(1).toLowerCase() },
    { accessorKey: 'volume', header: 'VOLUME', cell: info => info.getValue()?.toLocaleString() || '-' },
    {
      accessorKey: 'open_interest',
      header: 'OPEN INTEREST',
      cell: info => {
        const val = info.getValue() || 0;
        const chg = info.row.original.change_in_oi || 0;
        return (
          <div className="flex flex-col">
            <span className="font-bold text-[#f8fafc]">{val.toLocaleString()}</span>
            <span className={chg >= 0 ? 'text-[#34d399]' : 'text-[#f87171] text-xs'}>
              ({chg >= 0 ? '+' : ''}{chg})
            </span>
          </div>
        );
      }
    },
    {
      accessorKey: 'implied_volatility',
      header: 'IMPLIED VOLATILITY',
      cell: info => info.getValue() ? `${info.getValue()}%` : '-'
    },
  ], []);

  const table = useReactTable({
    data: filteredData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const exportCSV = () => {
    const headers = columns.map(c => c.header).join(',');
    const rows = filteredData.map(row =>
      columns.map(c => {
        const val = row[c.accessorKey];
        return typeof val === 'string' ? `"${val}"` : val;
      }).join(',')
    ).join('\n');
    const blob = new Blob([`${headers}\n${rows}`], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${symbol}_options.csv`;
    a.click();
  };

  if (loading && !data) return <div className="p-10 text-center text-slate-400 font-bold animate-pulse">Loading {symbol} Options...</div>;

  return (
    <div className="bg-transparent text-[#cbd5e1] font-sans min-h-screen animate-in fade-in duration-500">
      {/* HEADER TITLE */}
      <div className="py-2 px-1">
        <h1 className="text-xl font-bold text-[#f8fafc] flex items-center gap-3">
          {symbol} <span className="text-xs font-medium text-[#94a3b8] uppercase tracking-widest bg-white/5 px-3 py-1 rounded-full">Options List</span>
        </h1>
      </div>

      {/* FILTER BAR */}
      <div className="mt-4 p-5 flex flex-wrap items-end gap-5 bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 shadow-xl">
        {/* Expiry */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-black text-[#64748b] uppercase tracking-widest">Options Date</label>
          <select
            value={expiry}
            onChange={(e) => { setExpiry(e.target.value); fetchData(e.target.value); }}
            className="bg-[#0f172a] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#e2e8f0] min-w-[140px] outline-none focus:border-[#3b82f6] transition-all cursor-pointer"
          >
            {data?.available_expiries?.map(exp => <option key={exp} value={exp}>{exp}</option>)}
          </select>
        </div>

        {/* Type */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-black text-[#64748b] uppercase tracking-widest">Options Type</label>
          <select
            value={optionType}
            onChange={(e) => setOptionType(e.target.value)}
            className="bg-[#0f172a] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#e2e8f0] min-w-[140px] outline-none focus:border-[#3b82f6] transition-all cursor-pointer"
          >
            <option>All</option>
            <option value="CALL">Calls</option>
            <option value="PUT">Puts</option>
          </select>
        </div>

        {/* Moneyness */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-black text-[#64748b] uppercase tracking-widest">Moneyness</label>
          <select
            value={moneyness}
            onChange={(e) => setMoneyness(e.target.value)}
            className="bg-[#0f172a] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#e2e8f0] min-w-[120px] outline-none focus:border-[#3b82f6] transition-all cursor-pointer"
          >
            <option>All</option>
            <option>ITM</option>
            <option>OTM</option>
          </select>
        </div>

        {/* Volume Filter */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-black text-[#64748b] uppercase tracking-widest">Volume Filter</label>
          <select
            value={volumeFilter}
            onChange={(e) => setVolumeFilter(e.target.value)}
            className="bg-[#0f172a] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#e2e8f0] min-w-[140px] outline-none focus:border-[#3b82f6] transition-all cursor-pointer"
          >
            <option>All</option>
            <option>With Volume</option>
          </select>
        </div>

        {/* Strike Range */}
        <div className="flex items-center gap-2">
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-black text-[#64748b] uppercase tracking-widest">Strike Min</label>
            <input
              type="number"
              value={strikeMin}
              onChange={(e) => setStrikeMin(e.target.value)}
              className="bg-[#0f172a] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#e2e8f0] w-[100px] outline-none focus:border-[#3b82f6] transition-all"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-black text-[#64748b] uppercase tracking-widest">Strike Max</label>
            <input
              type="number"
              value={strikeMax}
              onChange={(e) => setStrikeMax(e.target.value)}
              className="bg-[#0f172a] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#e2e8f0] w-[100px] outline-none focus:border-[#3b82f6] transition-all"
            />
          </div>
        </div>

        {/* Export */}
        <button
          onClick={exportCSV}
          className="ml-auto flex items-center gap-2 bg-white/10 hover:bg-[#3b82f6] text-[#e2e8f0] px-5 py-2.5 rounded-xl font-bold text-xs transition-all shadow-lg active:scale-95 border border-white/5"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
          EXPORT DATA
        </button>
      </div>

      {/* TABLE */}
      <div className="mt-6 overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-white/10 border-b border-white/5">
                {table.getHeaderGroups()[0].headers.map(header => (
                  <th key={header.id} className="px-6 py-4 text-left text-[11px] font-black text-[#94a3b8] uppercase tracking-widest">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {table.getRowModel().rows.map(row => (
                <tr key={row.id} className="hover:bg-white/5 transition-colors group">
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-6 py-4 text-sm text-[#e2e8f0] font-medium group-hover:text-[#3b82f6] transition-colors">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {filteredData.length === 0 && (
        <div className="p-20 text-center text-slate-400 italic">No options match your current filters.</div>
      )}
    </div>
  );
};

export default OptionsChain;
