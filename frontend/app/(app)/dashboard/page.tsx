"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";
import type { DashboardStats, Agent, FlaggedAccount, PREvent } from "@/lib/types";
import { Shield, CheckCircle, XCircle, Activity, AlertTriangle, GitBranch, ArrowRight, Clock } from "lucide-react";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [flagged, setFlagged] = useState<FlaggedAccount[]>([]);
  const [processingStatus, setProcessingStatus] = useState<any[]>([]);
  const [events, setEvents] = useState<PREvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = () => {
    setLoading(true);
    Promise.all([
      api.getStats(),
      api.listAgents(),
      api.listFlaggedAccounts(),
      api.listProcessingStatus({ limit: 10 }),
      api.listEvents({ limit: 10 }),
    ])
      .then(([s, a, f, ps, ev]) => {
        setStats(s);
        setAgents(a.slice(0, 5)); // Show latest 5 agents
        setFlagged(f.slice(0, 5)); // Show latest 5 flagged accounts
        setProcessingStatus(ps);
        setEvents(ev);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadStats();
  }, []);

  // Auto-refresh processing status and events every 3 seconds
  useEffect(() => {
    if (!loading) {
      const interval = setInterval(() => {
        Promise.all([
          api.listProcessingStatus({ limit: 10 }),
          api.listEvents({ limit: 10 }),
        ])
          .then(([ps, ev]) => {
            setProcessingStatus(ps);
            setEvents(ev);
          })
          .catch((e) => console.error("Failed to refresh:", e));
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [loading]);

  const pct = (v: number) => `${Math.round(v * 100)}%`;

  const getProgressPercentage = (status: string) => {
    const progressMap: Record<string, number> = {
      detected: 10,
      queued: 20,
      hijack_proof_check: 40,
      spam_check: 60,
      malicious_code_check: 80,
      summary_generation: 90,
      completed: 100,
      failed: 0,
    };
    return progressMap[status] || 10;
  };

  const getStatusLabel = (status: string) => {
    const labelMap: Record<string, string> = {
      detected: "Detected",
      queued: "Queued",
      hijack_proof_check: "Hijack Check",
      spam_check: "Spam Check",
      malicious_code_check: "Malicious Code",
      summary_generation: "Summary",
      completed: "Complete",
      failed: "Failed",
    };
    return labelMap[status] || status;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of PRs processed across all your agents.
          </p>
        </div>
        <Button asChild>
          <Link href="/agents/new">New agent</Link>
        </Button>
      </div>

      {loading && <p className="text-muted-foreground">Loading…</p>}
      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total PRs" value={String(stats.total_prs)} icon={<GitBranch className="h-4 w-4" />} />
          <StatCard label="Approved" value={String(stats.approved)} tone="success" icon={<CheckCircle className="h-4 w-4" />} />
          <StatCard label="Declined" value={String(stats.declined)} tone="destructive" icon={<XCircle className="h-4 w-4" />} />
          <StatCard
            label="Flagged accounts"
            value={String(stats.flagged_accounts)}
            hint={stats.banned_accounts > 0 ? `${stats.banned_accounts} banned` : undefined}
            icon={<Shield className="h-4 w-4" />}
          />
          <StatCard label="Errors" value={String(stats.errors)} icon={<AlertTriangle className="h-4 w-4" />} />
          <StatCard label="Approval rate" value={pct(stats.approval_rate)} icon={<Activity className="h-4 w-4" />} />
        </div>
      )}

      {!loading && (processingStatus.length > 0 || events.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Recent PR Events & Processing
            </CardTitle>
            <CardDescription>
              All PRs across your agents with real-time processing progress.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {processingStatus.length === 0 && events.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No PRs detected yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-2 pr-4 font-medium">Date</th>
                      <th className="pb-2 pr-4 font-medium">PR #</th>
                      <th className="pb-2 pr-4 font-medium">Title</th>
                      <th className="pb-2 pr-4 font-medium">Author</th>
                      <th className="pb-2 pr-4 font-medium">Decision</th>
                      <th className="pb-2 pr-4 font-medium">Progress</th>
                      <th className="pb-2 pr-4 font-medium">Layer</th>
                      <th className="pb-2 font-medium">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Show processing statuses first */}
                    {processingStatus.slice(0, 10).map((status) => {
                      const progress = getProgressPercentage(status.status);
                      const isCompleted = status.status === "completed";
                      
                      return (
                        <tr 
                          key={status.id} 
                          className="border-b last:border-0 hover:bg-muted/50 cursor-pointer"
                          onClick={() => window.location.href = `/dashboard/pr/${status.agent_id}/${status.pr_number}`}
                        >
                          <td className="py-2 pr-4 text-muted-foreground">
                            {status.detected_at ? new Date(status.detected_at).toLocaleString() : "—"}
                          </td>
                          <td className="py-2 pr-4">
                            <span className="font-medium text-primary hover:underline">
                              #{status.pr_number}
                            </span>
                          </td>
                          <td className="py-2 pr-4 max-w-[200px] truncate">
                            {status.pr_title}
                          </td>
                          <td className="py-2 pr-4">{status.author_github}</td>
                          <td className="py-2 pr-4">
                            {isCompleted ? (
                              <Badge variant={status.final_decision === "approved" ? "success" : "destructive"}>
                                {status.final_decision}
                              </Badge>
                            ) : (
                              <Badge variant="secondary">
                                {getStatusLabel(status.status)}
                              </Badge>
                            )}
                          </td>
                          <td className="py-2 pr-4 min-w-[150px]">
                            <div className="flex items-center gap-2">
                              <div className="h-2 w-24 bg-secondary rounded-full overflow-hidden">
                                <div
                                  className={`h-full transition-all duration-500 ease-out ${isCompleted ? 'bg-green-500' : 'bg-primary'}`}
                                  style={{ width: `${progress}%` }}
                                />
                              </div>
                              <span className="text-xs text-muted-foreground w-8">
                                {progress}%
                              </span>
                              {isCompleted && (
                                <Badge variant="success" className="text-xs">✓</Badge>
                              )}
                            </div>
                          </td>
                          <td className="py-2 pr-4">
                            {status.final_decision ? (status.final_decision === "approved" ? "—" : "pipeline") : "—"}
                          </td>
                          <td className="py-2 max-w-[200px]">
                            {status.error_message ? (
                              <Badge variant="destructive" className="text-xs" title={status.error_message}>
                                Error
                              </Badge>
                            ) : (
                              <span className="text-muted-foreground truncate block">
                                {status.decline_reason || "—"}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                    
                    {/* Show completed events that don't have active processing status */}
                    {events
                      .slice(0, 10)
                      .filter(ev => !processingStatus.find(ps => ps.pr_number === ev.pr_number))
                      .map((ev) => (
                        <tr 
                          key={ev.id} 
                          className="border-b last:border-0 hover:bg-muted/50 cursor-pointer"
                          onClick={() => window.location.href = `/dashboard/pr/${ev.agent_id}/${ev.pr_number}`}
                        >
                          <td className="py-2 pr-4 text-muted-foreground">
                            {new Date(ev.created_at).toLocaleString()}
                          </td>
                          <td className="py-2 pr-4">
                            <span className="font-medium text-primary hover:underline">
                              #{ev.pr_number}
                            </span>
                          </td>
                          <td className="py-2 pr-4 max-w-[200px] truncate">
                            —
                          </td>
                          <td className="py-2 pr-4">{ev.author_github}</td>
                          <td className="py-2 pr-4">
                            <Badge
                              variant={
                                ev.decision === "approved"
                                  ? "success"
                                  : "destructive"
                              }
                            >
                              {ev.decision}
                            </Badge>
                          </td>
                          <td className="py-2 pr-4 min-w-[150px]">
                            <div className="flex items-center gap-2">
                              <div className="h-2 w-24 bg-green-500 rounded-full overflow-hidden">
                                <div className="h-full bg-green-500" style={{ width: "100%" }} />
                              </div>
                              <span className="text-xs text-muted-foreground w-8">100%</span>
                              <Badge variant="success" className="text-xs">✓</Badge>
                            </div>
                          </td>
                          <td className="py-2 pr-4">
                            {ev.layer_caught ?? "—"}
                          </td>
                          <td className="py-2 text-muted-foreground max-w-[200px] truncate">
                            {ev.reason ?? "—"}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
            <Button asChild variant="outline" className="w-full mt-4">
              <Link href="/dashboard/events" className="flex items-center gap-2">
                View all PRs
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {!loading && agents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Latest Agents
            </CardTitle>
            <CardDescription>
              Your most recently created agents.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {agents.map((agent) => (
                <Link
                  key={agent.id}
                  href={`/agents/${agent.id}`}
                  className="block p-3 rounded-lg border hover:border-primary/50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <div className="font-medium">{agent.name}</div>
                      <div className="text-sm text-muted-foreground font-mono">{agent.repo_full_name}</div>
                    </div>
                    <Badge variant={agent.is_active ? "success" : "secondary"} className="text-xs">
                      {agent.is_active ? "Active" : "Paused"}
                    </Badge>
                  </div>
                </Link>
              ))}
            </div>
            <Button asChild variant="outline" className="w-full mt-4">
              <Link href="/agents" className="flex items-center gap-2">
                View all agents
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {!loading && flagged.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Latest Flagged Accounts
            </CardTitle>
            <CardDescription>
              GitHub accounts recently flagged by your agents.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {flagged.map((f) => (
                <div
                  key={f.github_username}
                  className="flex items-center justify-between p-3 rounded-lg border"
                >
                  <div className="flex items-center gap-2">
                    <a
                      href={`https://github.com/${f.github_username}`}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-primary hover:underline"
                    >
                      {f.github_username}
                    </a>
                    <Badge variant="outline" className="text-xs">
                      {f.flag_count} flags
                    </Badge>
                    {f.account_status === "banned" && (
                      <AlertTriangle className="h-4 w-4 text-destructive" />
                    )}
                  </div>
                  <Badge
                    variant={f.account_status === "banned" ? "destructive" : "secondary"}
                    className="text-xs"
                  >
                    {f.account_status}
                  </Badge>
                </div>
              ))}
            </div>
            <Button asChild variant="outline" className="w-full mt-4">
              <Link href="/flagged" className="flex items-center gap-2">
                View all flagged accounts
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {!loading && agents.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              No agents yet
            </CardTitle>
            <CardDescription>
              Create your first agent to start reviewing PRs automatically.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/agents/new">Create agent</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  tone,
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "success" | "destructive";
  icon?: React.ReactNode;
}) {
  const valueClass =
    tone === "success"
      ? "text-emerald-500"
      : tone === "destructive"
        ? "text-destructive"
        : "text-foreground";
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardDescription>{label}</CardDescription>
          {icon && <div className="text-muted-foreground">{icon}</div>}
        </div>
        <CardTitle className={`text-2xl ${valueClass}`}>{value}</CardTitle>
      </CardHeader>
      {hint && (
        <CardContent className="pt-0 text-xs text-muted-foreground">{hint}</CardContent>
      )}
    </Card>
  );
}
