'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Mail,
  MessageSquare,
  PhoneCall,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';

interface Escalation {
  id: number;
  user_id: string;
  caller_name: string;
  reason_category: string;
  what_happened: string;
  what_agent_checked: string;
  urgency: string;
  language: string;
  preferred_followup: string;
  status: string;
  created_at: string;
}

export default function EscalationsPage() {
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'OPEN' | 'HIGH' | 'RESOLVED'>('ALL');
  const [resolvingId, setResolvingId] = useState<number | null>(null);

  const fetchEscalations = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/escalations');
      const json = await res.json();
      if (json.success && Array.isArray(json.data)) {
        setEscalations(json.data);
      }
    } catch (err) {
      console.error('Failed to load escalations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEscalations();
    const interval = setInterval(fetchEscalations, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleResolve = async (id: number) => {
    setResolvingId(id);
    try {
      const res = await fetch('/api/escalations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, action: 'resolve' }),
      });
      const json = await res.json();
      if (json.success) {
        setEscalations((prev) =>
          prev.map((item) => (item.id === id ? { ...item, status: 'RESOLVED' } : item))
        );
      }
    } catch (err) {
      console.error('Error resolving ticket:', err);
    } finally {
      setResolvingId(null);
    }
  };

  const filtered = escalations.filter((item) => {
    if (filterStatus === 'OPEN') return item.status === 'OPEN';
    if (filterStatus === 'RESOLVED') return item.status === 'RESOLVED';
    if (filterStatus === 'HIGH') return item.urgency === 'HIGH' || item.urgency === 'URGENT';
    return true;
  });

  const totalCount = escalations.length;
  const openCount = escalations.filter((i) => i.status === 'OPEN').length;
  const highUrgencyCount = escalations.filter(
    (i) => (i.urgency === 'HIGH' || i.urgency === 'URGENT') && i.status === 'OPEN'
  ).length;
  const resolvedCount = escalations.filter((i) => i.status === 'RESOLVED').length;

  const getFollowupIcon = (method: string) => {
    const lower = (method || '').toLowerCase();
    if (lower.includes('sms'))
      return <MessageSquare className="mr-1 inline h-4 w-4 text-cyan-400" />;
    if (lower.includes('email')) return <Mail className="mr-1 inline h-4 w-4 text-purple-400" />;
    return <PhoneCall className="mr-1 inline h-4 w-4 text-emerald-400" />;
  };

  return (
    <div className="min-h-screen bg-slate-950 p-4 font-sans text-slate-100 md:p-8">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Header */}
        <div className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-5 md:flex-row md:items-center">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="inline-flex items-center rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-400 transition hover:text-white"
              >
                <ArrowLeft className="mr-1 h-3.5 w-3.5" /> Back to Agent
              </Link>
              <span className="rounded-full border border-red-800 bg-red-950 px-2.5 py-0.5 text-xs font-semibold tracking-wide text-red-400">
                DAY 7 FEATURE
              </span>
            </div>
            <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-white md:text-3xl">
              <ShieldAlert className="h-7 w-7 text-red-500" />
              Human Escalation Dashboard
            </h1>
            <p className="text-sm text-slate-400">
              Real-time monitoring of caller assistance requests, fraud alerts & decision
              escalations.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchEscalations}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-slate-800 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh Data
            </button>
          </div>
        </div>

        {/* Metrics Banner */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="space-y-1 rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4">
            <p className="text-xs font-medium text-slate-400">Total Requests</p>
            <p className="text-2xl font-extrabold text-white">{totalCount}</p>
          </div>
          <div className="space-y-1 rounded-2xl border border-amber-800/40 bg-amber-950/20 p-4">
            <p className="text-xs font-medium text-amber-400">Open Requests</p>
            <p className="text-2xl font-extrabold text-amber-300">{openCount}</p>
          </div>
          <div className="space-y-1 rounded-2xl border border-red-800/50 bg-red-950/30 p-4">
            <p className="flex items-center gap-1 text-xs font-medium text-red-400">
              <AlertTriangle className="h-3.5 w-3.5" /> High Urgency / Fraud
            </p>
            <p className="text-2xl font-extrabold text-red-400">{highUrgencyCount}</p>
          </div>
          <div className="space-y-1 rounded-2xl border border-emerald-800/40 bg-emerald-950/20 p-4">
            <p className="text-xs font-medium text-emerald-400">Resolved Tickets</p>
            <p className="text-2xl font-extrabold text-emerald-400">{resolvedCount}</p>
          </div>
        </div>

        {/* Filter Navigation */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
          {(['ALL', 'OPEN', 'HIGH', 'RESOLVED'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilterStatus(tab)}
              className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold tracking-wide transition ${
                filterStatus === tab
                  ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/20'
                  : 'border border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
              }`}
            >
              {tab === 'ALL' && 'All Requests'}
              {tab === 'OPEN' && `Open (${openCount})`}
              {tab === 'HIGH' && `Fraud & High Urgency (${highUrgencyCount})`}
              {tab === 'RESOLVED' && `Resolved (${resolvedCount})`}
            </button>
          ))}
        </div>

        {/* Tickets Listing */}
        {filtered.length === 0 ? (
          <div className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center">
            <ShieldCheck className="mx-auto h-12 w-12 text-slate-600" />
            <h3 className="text-lg font-semibold text-slate-300">No Escalation Requests Found</h3>
            <p className="mx-auto max-w-md text-sm text-slate-500">
              When the voice agent detects fraud or a complex financial decision requiring human
              intervention, the summarized request will appear here in real-time.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {filtered.map((item) => {
              const isHigh = item.urgency === 'HIGH' || item.urgency === 'URGENT';
              const isResolved = item.status === 'RESOLVED';

              return (
                <div
                  key={item.id}
                  className={`relative space-y-4 rounded-2xl border p-5 transition-all ${
                    isResolved
                      ? 'border-slate-800/60 bg-slate-900/40 opacity-75'
                      : isHigh
                        ? 'border-red-800/60 bg-gradient-to-r from-red-950/40 via-slate-900/90 to-slate-900 shadow-lg shadow-red-950/20'
                        : 'border-slate-800 bg-slate-900/80 shadow-md'
                  }`}
                >
                  {/* Card Header */}
                  <div className="flex flex-col justify-between gap-2 border-b border-slate-800/80 pb-3 sm:flex-row sm:items-center">
                    <div className="flex items-center gap-3">
                      <span className="rounded border border-slate-800 bg-slate-950 px-2 py-0.5 font-mono text-xs text-slate-500">
                        #{item.id}
                      </span>
                      <h3 className="flex items-center gap-2 text-base font-bold text-white">
                        <UserCheck className="h-4 w-4 text-emerald-400" />
                        {item.caller_name}
                        <span className="font-mono text-xs font-normal text-slate-400">
                          ({item.user_id})
                        </span>
                      </h3>
                    </div>

                    <div className="flex items-center gap-2">
                      {isHigh ? (
                        <span className="inline-flex animate-pulse items-center rounded-full border border-red-700 bg-red-950 px-2.5 py-1 text-xs font-bold text-red-400">
                          <AlertTriangle className="mr-1 h-3 w-3" /> URGENT / FRAUD
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full border border-amber-800 bg-amber-950 px-2.5 py-1 text-xs font-semibold text-amber-300">
                          NORMAL DECISION
                        </span>
                      )}

                      {isResolved ? (
                        <span className="inline-flex items-center rounded-full border border-emerald-800 bg-emerald-950 px-2.5 py-1 text-xs font-semibold text-emerald-400">
                          <CheckCircle2 className="mr-1 h-3 w-3" /> RESOLVED
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-300">
                          OPEN
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Incident Summary & Verification */}
                  <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
                    <div className="space-y-1 rounded-xl border border-slate-800/80 bg-slate-950/60 p-3.5">
                      <p className="flex items-center gap-1 text-xs font-semibold text-slate-400">
                        📌 What Happened (Issue Summary):
                      </p>
                      <p className="leading-relaxed font-medium text-slate-200">
                        {item.what_happened}
                      </p>
                    </div>

                    <div className="space-y-1 rounded-xl border border-slate-800/80 bg-slate-950/60 p-3.5">
                      <p className="flex items-center gap-1 text-xs font-semibold text-slate-400">
                        🔍 What Agent Checked:
                      </p>
                      <p className="leading-relaxed text-slate-300">
                        {item.what_agent_checked ||
                          'Verified identity and initial conversation context.'}
                      </p>
                    </div>
                  </div>

                  {/* Metadata Footer & Action */}
                  <div className="flex flex-col justify-between gap-3 pt-1 text-xs text-slate-400 sm:flex-row sm:items-center">
                    <div className="flex flex-wrap items-center gap-4">
                      <span>
                        <strong>Category:</strong> {item.reason_category}
                      </span>
                      <span>
                        <strong>Language:</strong> {item.language}
                      </span>
                      <span className="flex items-center">
                        <strong>Follow-up:</strong>&nbsp;
                        {getFollowupIcon(item.preferred_followup)}
                        {item.preferred_followup}
                      </span>
                      <span className="flex items-center text-slate-500">
                        <Clock className="mr-1 h-3 w-3" />
                        {new Date(item.created_at).toLocaleString()}
                      </span>
                    </div>

                    {!isResolved && (
                      <button
                        onClick={() => handleResolve(item.id)}
                        disabled={resolvingId === item.id}
                        className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-emerald-600/20 transition hover:bg-emerald-500 disabled:opacity-50"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {resolvingId === item.id ? 'Updating...' : 'Mark as Resolved'}
                      </button>
                    )}
                  </div>

                  {/* Privacy Badge */}
                  <div className="flex items-center gap-1 border-t border-slate-800/40 pt-1 text-[11px] text-slate-500">
                    <ShieldCheck className="h-3 w-3 text-emerald-500" />
                    <span>
                      Privacy Guardrail Active: Sensitive credentials (PIN, OTP, passwords)
                      automatically scrubbed.
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
