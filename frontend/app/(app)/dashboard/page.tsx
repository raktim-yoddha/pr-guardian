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
import type { DashboardStats, Agent, FlaggedAccount } from "@/lib/types";
import { Shield, CheckCircle, XCircle, Activity, AlertTriangle, GitBranch, ArrowRight, Clock } from "lucide-react";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [flagged, setFlagged] = useState<FlaggedAccount[]>([]);
  const [processingStatus, setProcessingStatus] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = () => {
    setLoading(true);
    Promise.all([
      api.getStats(),
      api.listAgents(),
      api.listFlaggedAccounts(),
      api.listProcessingStatus({ limit: 10 }),
    ])
      .then(([s, a, f, ps]) => {
        setStats(s);
        setAgents(a.slice(0, 5)); // Show latest 5 agents
        setFlagged(f.slice(0, 5)); // Show latest 5 flagged accounts
        setProcessingStatus(ps);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadStats();
  }, []);

  // Auto-refresh processing status every 3 seconds (only processing status, not full reload)
  useEffect(() => {
    if (!loading) {
      const interval = setInterval(() => {
        api.listProcessingStatus({ limit: 10 })
          .then(setProcessingStatus)
          .catch((e) => console.error("Failed to refresh processing status:", e));
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

      {!loading && processingStatus.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Recent PR Processing
              </h2>
              <p className="text-muted-foreground">
                Latest PRs being processed through the pipeline
              </p>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {processingStatus.slice(0, 6).map((ps) => {
              const progress = getProgressPercentage(ps.status);
              const isCompleted = ps.status === "completed";
              
              return (
                <Link
                  key={ps.id}
                  href={`/agents/${ps.agent_id}`}
                  className="block"
                >
                  <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="outline" className="text-xs">#{ps.pr_number}</Badge>
                            <Badge 
                              variant={isCompleted ? "success" : ps.status === "failed" ? "destructive" : "secondary"}
                              className="text-xs"
                            >
                              {getStatusLabel(ps.status)}
                            </Badge>
                          </div>
                          <CardTitle className="text-sm truncate">{ps.pr_title}</CardTitle>
                          <CardDescription className="text-xs">
                            by {ps.author_github}
                          </CardDescription>
                        </div>
                        {isCompleted && (
                          <Badge variant="success" className="text-xs shrink-0">✓</Badge>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="space-y-2">
                        <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all duration-500 ease-out ${isCompleted ? 'bg-green-500' : 'bg-primary'}`}
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>{progress}% complete</span>
                          <span>{ps.detected_at ? new Date(ps.detected_at).toLocaleDateString() : ""}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
          <Button asChild variant="outline" className="w-full mt-4">
            <Link href="/dashboard/events" className="flex items-center gap-2">
              View all PRs
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
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
