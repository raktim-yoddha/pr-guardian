"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiError, api } from "@/lib/api";
import type { Agent, PREvent } from "@/lib/types";

interface PRProcessingStatus {
  id: number;
  agent_id: number;
  pr_number: number;
  pr_url: string;
  pr_title: string;
  author_github: string;
  status: string;
  layer_results: any;
  final_decision: string | null;
  decline_reason: string | null;
  error_message: string | null;
  detected_at: string | null;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const agentId = Number(params.id);

  const [agent, setAgent] = useState<Agent | null>(null);
  const [events, setEvents] = useState<PREvent[]>([]);
  const [processingStatuses, setProcessingStatuses] = useState<PRProcessingStatus[]>([]);
  const [ingestionLogs, setIngestionLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const logsPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadAgent = useCallback(async () => {
    try {
      const a = await api.getAgent(agentId);
      setAgent(a);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load agent");
    }
  }, [agentId]);

  const loadProcessingStatus = useCallback(async () => {
    try {
      const statuses = await api.listProcessingStatus({ agent_id: agentId, limit: 50 });
      setProcessingStatuses(statuses);
    } catch (e) {
      console.error("Failed to load processing status:", e);
    }
  }, [agentId]);

  const loadIngestionLogs = useCallback(async () => {
    try {
      const logs = await api.getAgentIngestionLogs(agentId, 50);
      setIngestionLogs(logs);
      
      // Stop polling if ingestion is done or failed
      if (agent && (agent.ingestion_status === "done" || agent.ingestion_status === "failed")) {
        if (logsPollRef.current) {
          clearInterval(logsPollRef.current);
          logsPollRef.current = null;
        }
      }
    } catch (e) {
      console.error("Failed to load ingestion logs:", e);
    }
  }, [agentId, agent]);

  async function load() {
    try {
      const [a, evs, statuses, logs] = await Promise.all([
        api.getAgent(agentId),
        api.listEvents({ agent_id: agentId, limit: 50 }),
        api.listProcessingStatus({ agent_id: agentId, limit: 50 }),
        api.getAgentIngestionLogs(agentId, 50),
      ]);
      setAgent(a);
      setEvents(evs);
      setProcessingStatuses(statuses);
      setIngestionLogs(logs);
      // Set syncing state based on agent status
      setSyncing(a.ingestion_status === "running" || a.ingestion_status === "pending");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load agent");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId]);

  // Auto-refresh processing status every 2 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadProcessingStatus();
    }, 2000);
    return () => clearInterval(interval);
  }, [loadProcessingStatus]);

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

  const getProcessingStatusForPR = (prNumber: number) => {
    return processingStatuses.find(ps => ps.pr_number === prNumber);
  };

  async function handleToggle() {
    if (!agent) return;
    setToggling(true);
    try {
      const updated = await api.updateAgent(agent.id, {
        is_active: !agent.is_active,
      });
      setAgent(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to update agent");
    } finally {
      setToggling(false);
    }
  }

  async function handleDelete() {
    if (!agent) return;
    if (!window.confirm(`Delete agent "${agent.name}"? This cannot be undone.`)) {
      return;
    }
    try {
      await api.deleteAgent(agent.id);
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to delete agent");
    }
  }

  async function handleSync() {
    if (!agent) return;
    setSyncing(true);
    setError(null);
    try {
      const updated = await api.syncAgent(agent.id);
      setAgent(updated);
      // Reload logs after sync completes (since it's now synchronous)
      await loadIngestionLogs();
      await loadProcessingStatus();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to sync");
    } finally {
      setSyncing(false);
    }
  }

  async function handleCancelSync() {
    if (!agent) return;
    setCancelling(true);
    try {
      const updated = await api.cancelAgentSync(agent.id);
      setAgent(updated);
      setSyncing(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to cancel sync");
    } finally {
      setCancelling(false);
    }
  }

  const handleOpenLogsDialog = () => {
    setShowLogsDialog(true);
    loadIngestionLogs();
    // Start polling for logs
    if (agent && (agent.ingestion_status === "running" || agent.ingestion_status === "pending")) {
      if (logsPollRef.current) clearInterval(logsPollRef.current);
      logsPollRef.current = setInterval(() => void loadIngestionLogs(), 1000);
    }
  };

  const handleCloseLogsDialog = () => {
    setShowLogsDialog(false);
    if (logsPollRef.current) {
      clearInterval(logsPollRef.current);
      logsPollRef.current = null;
    }
  };

  if (loading) return <p className="text-muted-foreground">Loading…</p>;
  if (error && !agent) {
    return (
      <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
        {error}
      </div>
    );
  }
  if (!agent) return null;

  const ingestionRunning =
    agent.ingestion_status === "running" || agent.ingestion_status === "pending";

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back to agents
        </Link>
      </div>

      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{agent.name}</h1>
            <Badge variant={agent.is_active ? "success" : "secondary"}>
              {agent.is_active ? "Active" : "Paused"}
            </Badge>
          </div>
          <p className="font-mono text-sm text-muted-foreground">
            {agent.repo_full_name}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleOpenLogsDialog}
          >
            Check Sync
          </Button>
          {syncing ? (
            <Button
              variant="destructive"
              onClick={handleCancelSync}
              disabled={cancelling}
            >
              {cancelling ? "Cancelling…" : "Cancel Sync"}
            </Button>
          ) : (
            <Button
              variant="outline"
              onClick={handleSync}
              disabled={ingestionRunning}
            >
              {ingestionRunning ? "Syncing…" : "Re-sync Knowledge Base"}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={handleToggle}
            disabled={toggling}
          >
            {agent.is_active ? "Pause" : "Resume"}
          </Button>
          <Button asChild variant="outline">
            <Link href={`/agents/${agent.id}/settings`}>Settings</Link>
          </Button>
          <Button variant="destructive" onClick={handleDelete}>
            Delete
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>LLM</CardDescription>
            <CardTitle className="text-base capitalize">
              {agent.llm_provider}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Ingestion status</CardDescription>
            <div className="flex items-center gap-2">
              <CardTitle className="text-base capitalize">
                {agent.ingestion_status}
              </CardTitle>
              {ingestionRunning && (
                <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
              )}
            </div>
            {agent.last_ingested_at && (
              <p className="text-xs text-muted-foreground">
                Last synced{" "}
                {new Date(agent.last_ingested_at).toLocaleString()}
              </p>
            )}
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Knowledge chunks</CardDescription>
            <CardTitle className="text-base">{agent.chunk_count}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total events</CardDescription>
            <CardTitle className="text-base">{events.length}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>PR Events & Processing</CardTitle>
          <CardDescription>
            All PRs for this agent with real-time processing progress.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {events.length === 0 && processingStatuses.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No PRs detected yet. The agent will automatically detect open PRs after ingestion completes.
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
                  {processingStatuses.map((status) => {
                    const progress = getProgressPercentage(status.status);
                    const isCompleted = status.status === "completed";
                    
                    return (
                      <tr 
                        key={status.id} 
                        className="border-b last:border-0 hover:bg-muted/50 cursor-pointer"
                        onClick={() => router.push(`/agents/${agentId}/pr/${status.pr_number}`)}
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
                    .filter(ev => !processingStatuses.find(ps => ps.pr_number === ev.pr_number))
                    .map((ev) => (
                      <tr 
                        key={ev.id} 
                        className="border-b last:border-0 hover:bg-muted/50 cursor-pointer"
                        onClick={() => router.push(`/agents/${agentId}/pr/${ev.pr_number}`)}
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
        </CardContent>
      </Card>

      <Dialog open={showLogsDialog} onOpenChange={handleCloseLogsDialog}>
        <DialogContent className="max-w-5xl w-full">
          <DialogHeader>
            <DialogTitle>Ingestion Progress</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 max-h-[70vh] overflow-y-auto">
            {ingestionLogs.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No ingestion logs yet.
              </p>
            ) : (
              <>
                {/* Show current file progress prominently */}
                {(() => {
                  const fetchLog = ingestionLogs.find(l => l.step === "fetch_file");
                  if (fetchLog) {
                    return (
                      <div className="flex items-center gap-3 rounded-lg border p-4 bg-muted">
                        <div className="flex-1">
                          <p className="text-sm font-medium">{fetchLog.message}</p>
                          {fetchLog.current !== null && fetchLog.total !== null && (
                            <p className="text-xs text-muted-foreground mt-1">
                              {fetchLog.current}/{fetchLog.total} files
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  }
                  return null;
                })()}
                
                {/* Show other logs below */}
                {ingestionLogs.filter(l => l.step !== "fetch_file").slice().reverse().map((log) => (
                  <div
                    key={log.id}
                    className="flex items-start gap-3 rounded-lg border p-3 text-sm"
                  >
                    <div className="mt-0.5">
                      {log.status === "success" && (
                        <div className="h-2 w-2 rounded-full bg-green-500" />
                      )}
                      {log.status === "error" && (
                        <div className="h-2 w-2 rounded-full bg-red-500" />
                      )}
                      {log.status === "warning" && (
                        <div className="h-2 w-2 rounded-full bg-yellow-500" />
                      )}
                      {log.status === "info" && (
                        <div className="h-2 w-2 rounded-full bg-blue-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium capitalize text-muted-foreground">
                          {log.step.replace(/_/g, " ")}
                        </span>
                      </div>
                      <p className="mt-1 text-muted-foreground break-words">{log.message}</p>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
