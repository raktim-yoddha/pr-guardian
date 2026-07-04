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
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Agent, AgentStats, DashboardStats, FlaggedAccount } from "@/lib/types";
import { Shield, AlertTriangle, CheckCircle, XCircle, Clock, Activity, Users, GitBranch } from "lucide-react";

export default function DashboardPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [perAgent, setPerAgent] = useState<AgentStats[]>([]);
  const [flagged, setFlagged] = useState<FlaggedAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unflagging, setUnflagging] = useState<string | null>(null);

  // Filter by agent
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");

  const handleUnflag = async (username: string) => {
    setUnflagging(username);
    try {
      await api.unflagAccount(username);
      setFlagged(flagged.filter(f => f.github_username !== username));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to unflag account");
    } finally {
      setUnflagging(null);
    }
  };

  const loadStats = () => {
    setLoading(true);
    Promise.all([
      api.listAgents(),
      api.getStats(selectedAgentId ? parseInt(selectedAgentId) : undefined),
      api.getPerAgentStats(),
      api.listFlaggedAccounts(selectedAgentId ? parseInt(selectedAgentId) : undefined),
    ])
      .then(([a, s, pa, f]) => {
        setAgents(a);
        setStats(s);
        setPerAgent(pa);
        setFlagged(f);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadStats();
  }, [selectedAgentId]);

  const pct = (v: number) => `${Math.round(v * 100)}%`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of PRs processed across all your agents.
          </p>
        </div>
        <div className="flex gap-2">
          <div className="flex items-center gap-2">
            <Label htmlFor="agent-filter">Filter by Agent:</Label>
            <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
              <SelectTrigger id="agent-filter" className="w-[200px]">
                <SelectValue placeholder="All agents" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All agents</SelectItem>
                {agents.map((a) => (
                  <SelectItem key={a.id} value={String(a.id)}>
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button asChild>
            <Link href="/agents/new">New agent</Link>
          </Button>
        </div>
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
          <StatCard label="Active agents" value={String(agents.filter((a) => a.is_active).length)} icon={<Users className="h-4 w-4" />} />
          <StatCard label="Total agents" value={String(agents.length)} icon={<Clock className="h-4 w-4" />} />
        </div>
      )}

      {!loading && agents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Your agents</CardTitle>
            <CardDescription>
              Each agent guards one GitHub repository.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {agents.map((agent) => {
                const s = perAgent.find((p) => p.agent_id === agent.id);
                return (
                  <Link key={agent.id} href={`/agents/${agent.id}`} className="block">
                    <Card className="h-full transition-colors hover:border-primary/50">
                      <CardHeader>
                        <div className="flex items-start justify-between gap-2">
                          <div className="space-y-1">
                            <CardTitle className="text-lg">{agent.name}</CardTitle>
                            <CardDescription className="font-mono">
                              {agent.repo_full_name}
                            </CardDescription>
                          </div>
                          <Badge variant={agent.is_active ? "success" : "secondary"}>
                            {agent.is_active ? "Active" : "Paused"}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-2 text-sm text-muted-foreground">
                        <div className="flex justify-between">
                          <span>PRs</span>
                          <span className="font-medium text-foreground">
                            {s ? `${s.approved}/${s.total_prs} approved` : "—"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>LLM</span>
                          <span className="font-medium text-foreground">
                            {agent.llm_provider}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Ingestion</span>
                          <span className="font-medium text-foreground capitalize">
                            {agent.ingestion_status}
                          </span>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {!loading && agents.length === 0 && !error && (
        <Card>
          <CardHeader>
            <CardTitle>No agents yet</CardTitle>
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

      {!loading && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Flagged accounts
            </CardTitle>
            <CardDescription>
              GitHub accounts flagged by your agents&apos; pipelines. You can manually remove flags if the AI was wrong.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {flagged.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Shield className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-sm text-muted-foreground">
                  No flagged accounts yet.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-3 pr-4 font-medium">Username</th>
                      <th className="pb-3 pr-4 font-medium">Flags</th>
                      <th className="pb-3 pr-4 font-medium">Status</th>
                      <th className="pb-3 pr-4 font-medium">First seen</th>
                      <th className="pb-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {flagged.map((f) => (
                      <tr key={f.github_username} className="border-b last:border-0 hover:bg-muted/50 transition-colors">
                        <td className="py-3 pr-4 font-medium">
                          <a
                            href={`https://github.com/${f.github_username}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary hover:underline flex items-center gap-1"
                          >
                            {f.github_username}
                            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </a>
                        </td>
                        <td className="py-3 pr-4">
                          <Badge variant="outline" className="font-mono">
                            {f.flag_count}
                          </Badge>
                        </td>
                        <td className="py-3 pr-4">
                          <Badge
                            variant={f.account_status === "banned" ? "destructive" : "secondary"}
                            className={f.account_status === "active" ? "bg-green-500/10 text-green-500 hover:bg-green-500/20" : ""}
                          >
                            {f.account_status}
                          </Badge>
                        </td>
                        <td className="py-3 pr-4 text-muted-foreground">
                          {new Date(f.first_seen).toLocaleDateString()}
                        </td>
                        <td className="py-3">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleUnflag(f.github_username)}
                            disabled={unflagging === f.github_username}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            {unflagging === f.github_username ? (
                              "Removing..."
                            ) : (
                              <>
                                <Shield className="h-4 w-4 mr-1" />
                                Unflag
                              </>
                            )}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
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
