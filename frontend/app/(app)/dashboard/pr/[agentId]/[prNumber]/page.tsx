"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import type { PRDetail } from "@/lib/types";
import { ArrowLeft, CheckCircle, XCircle, AlertCircle, Clock, GitBranch, User, ExternalLink } from "lucide-react";

export default function PRDetailPage() {
  const params = useParams();
  const agentId = parseInt(params.agentId as string);
  const prNumber = parseInt(params.prNumber as string);

  const [detail, setDetail] = useState<PRDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDetail = async () => {
      try {
        const data = await api.getPRDetail(agentId, prNumber);
        setDetail(data);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load PR details");
      } finally {
        setLoading(false);
      }
    };

    loadDetail();
  }, [agentId, prNumber]);

  // Separate effect for polling - only poll when not loading and not completed/failed
  useEffect(() => {
    if (!loading && detail && 
        detail.processing_status?.status !== "completed" && 
        detail.processing_status?.status !== "failed") {
      const interval = setInterval(() => {
        api.getPRDetail(agentId, prNumber)
          .then(setDetail)
          .catch((e) => console.error("Failed to refresh PR details:", e));
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [loading, detail?.processing_status?.status, agentId, prNumber]);

  const getProgressPercentage = () => {
    const status = detail?.processing_status?.status;
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
    return progressMap[status || "detected"] || 10;
  };

  const getStatusLabel = () => {
    const status = detail?.processing_status?.status;
    const labelMap: Record<string, string> = {
      detected: "PR Detected",
      queued: "Queued for Processing",
      hijack_proof_check: "Checking for Hijack Attempts",
      spam_check: "Analyzing for Spam",
      malicious_code_check: "Scanning for Malicious Code",
      summary_generation: "Generating Summary",
      completed: "Processing Complete",
      failed: "Processing Failed",
    };
    return labelMap[status || "detected"] || "Unknown";
  };

  const getLayerResults = () => {
    return detail?.processing_status?.layer_results || {};
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/agents/${agentId}`}>
              <ArrowLeft className="h-4 w-4" />
              Back to Agent
            </Link>
          </Button>
        </div>
        <div className="flex items-center justify-center py-12">
          <div className="text-muted-foreground">Loading PR details…</div>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/agents/${agentId}`}>
              <ArrowLeft className="h-4 w-4" />
              Back to Agent
            </Link>
          </Button>
        </div>
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          {error || "PR not found"}
        </div>
      </div>
    );
  }

  const ps = detail.processing_status;
  const event = detail.event;
  const layerResults = getLayerResults();
  const progress = getProgressPercentage();
  const isCompleted = ps?.status === "completed";
  const isFailed = ps?.status === "failed";
  const isApproved = ps?.final_decision === "approved";
  const isDeclined = ps?.final_decision === "declined";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/agents/${agentId}`}>
              <ArrowLeft className="h-4 w-4" />
              Back to Agent
            </Link>
          </Button>
        </div>
        <Button variant="outline" size="sm" asChild>
          <a href={ps?.pr_url || "#"} target="_blank" rel="noreferrer">
            <ExternalLink className="h-4 w-4 mr-2" />
            View on GitHub
          </a>
        </Button>
      </div>

      {/* PR Header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="space-y-2 flex-1">
              <div className="flex items-center gap-2">
                <Badge variant="outline">
                  <GitBranch className="h-3 w-3 mr-1" />
                  #{ps?.pr_number}
                </Badge>
                <Badge variant={isCompleted ? "success" : isFailed ? "destructive" : "secondary"}>
                  {isCompleted ? (isApproved ? "Approved" : "Declined") : getStatusLabel()}
                </Badge>
              </div>
              <CardTitle className="text-xl">{ps?.pr_title}</CardTitle>
              <CardDescription className="flex items-center gap-4">
                <span className="flex items-center gap-1">
                  <User className="h-3 w-3" />
                  {ps?.author_github}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {ps?.detected_at ? new Date(ps.detected_at).toLocaleString() : "Unknown"}
                </span>
              </CardDescription>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Progress Bar */}
      {!isCompleted && !isFailed && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Processing Progress
            </CardTitle>
            <CardDescription>
              {getStatusLabel()} - {progress}%
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-500 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Detected</span>
                <span>Hijack Check</span>
                <span>Spam Check</span>
                <span>Malicious Code</span>
                <span>Summary</span>
                <span>Complete</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Final Decision */}
      {isCompleted && (
        <Card className={isApproved ? "border-green-500/50" : "border-red-500/50"}>
          <CardHeader>
            <CardTitle className={`flex items-center gap-2 ${isApproved ? "text-green-600" : "text-red-600"}`}>
              {isApproved ? (
                <>
                  <CheckCircle className="h-5 w-5" />
                  PR Approved
                </>
              ) : (
                <>
                  <XCircle className="h-5 w-5" />
                  PR Declined
                </>
              )}
            </CardTitle>
            <CardDescription>
              {isApproved
                ? "This PR passed all automated review layers"
                : ps?.decline_reason || "This PR was declined by the automated review pipeline"}
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {isFailed && (
        <Card className="border-orange-500/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-orange-600">
              <AlertCircle className="h-5 w-5" />
              Processing Failed
            </CardTitle>
            <CardDescription>
              {ps?.error_message || "An error occurred while processing this PR"}
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {/* Layer Results */}
      {Object.keys(layerResults).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Layer Analysis Results</CardTitle>
            <CardDescription>
              Detailed results from each detection layer
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {layerResults.hijack_proof && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 font-medium">
                  <Badge variant="outline">Hijack Proof Check</Badge>
                  <span className="text-sm text-muted-foreground">
                    {layerResults.hijack_proof.detected ? "⚠️ Detected" : "✓ Clean"}
                  </span>
                </div>
                {layerResults.hijack_proof.reason && (
                  <p className="text-sm text-muted-foreground pl-2">
                    {layerResults.hijack_proof.reason}
                  </p>
                )}
              </div>
            )}
            <Separator />
            {layerResults.spam && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 font-medium">
                  <Badge variant="outline">Spam Check</Badge>
                  <span className="text-sm text-muted-foreground">
                    Score: {layerResults.spam.score?.toFixed(2)}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {layerResults.spam.score > 0.75 ? "⚠️ Flagged" : "✓ Clean"}
                  </span>
                </div>
                {layerResults.spam.reason && (
                  <p className="text-sm text-muted-foreground pl-2">
                    {layerResults.spam.reason}
                  </p>
                )}
              </div>
            )}
            <Separator />
            {layerResults.malicious_code && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 font-medium">
                  <Badge variant="outline">Malicious Code Check</Badge>
                  <span className="text-sm text-muted-foreground">
                    {layerResults.malicious_code.detected ? "⚠️ Detected" : "✓ Clean"}
                  </span>
                </div>
                {layerResults.malicious_code.reason && (
                  <p className="text-sm text-muted-foreground pl-2">
                    {layerResults.malicious_code.reason}
                  </p>
                )}
                {layerResults.malicious_code.suspicious_lines && (
                  <div className="text-sm text-muted-foreground pl-2">
                    <p className="font-medium">Suspicious lines:</p>
                    <pre className="mt-1 p-2 bg-secondary rounded text-xs overflow-x-auto">
                      {layerResults.malicious_code.suspicious_lines.join("\n")}
                    </pre>
                  </div>
                )}
              </div>
            )}
            <Separator />
            {layerResults.summary && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 font-medium">
                  <Badge variant="outline">Summary Generation</Badge>
                  <span className="text-sm text-muted-foreground">✓ Generated</span>
                </div>
                {layerResults.summary.title && (
                  <div className="text-sm pl-2">
                    <p className="font-medium">Generated Title:</p>
                    <p className="text-muted-foreground">{layerResults.summary.title}</p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Generated Summary (for approved PRs) */}
      {isApproved && layerResults.summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Generated PR Summary</CardTitle>
            <CardDescription>
              AI-generated improvement to the PR description
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {layerResults.summary.title && (
              <div>
                <p className="font-medium mb-1">Improved Title:</p>
                <p className="text-sm bg-secondary p-2 rounded">{layerResults.summary.title}</p>
              </div>
            )}
            {layerResults.summary.body_preview && (
              <div>
                <p className="font-medium mb-1">Body Preview:</p>
                <p className="text-sm bg-secondary p-2 rounded whitespace-pre-wrap">
                  {layerResults.summary.body_preview}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Rejection Details (for declined PRs) */}
      {isDeclined && (
        <Card className="border-red-500/50">
          <CardHeader>
            <CardTitle className="text-lg text-red-600">Rejection Details</CardTitle>
            <CardDescription>
              Why this PR was declined
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="font-medium mb-1">Reason:</p>
              <p className="text-sm text-muted-foreground">{ps?.decline_reason}</p>
            </div>
            {event?.layer_caught && (
              <div>
                <p className="font-medium mb-1">Layer Caught:</p>
                <Badge variant="destructive">{event.layer_caught}</Badge>
              </div>
            )}
            {event?.reason && (
              <div>
                <p className="font-medium mb-1">Additional Context:</p>
                <p className="text-sm text-muted-foreground">{event.reason}</p>
              </div>
            )}
            {event?.layer_caught && layerResults[event.layer_caught]?.suspicious_lines && (
              <div>
                <p className="font-medium mb-1">Problematic Code Lines:</p>
                <pre className="text-sm bg-destructive/10 p-2 rounded text-destructive overflow-x-auto">
                  {layerResults[event.layer_caught].suspicious_lines.join("\n")}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Processing Timeline</CardTitle>
          <CardDescription>
            Timestamps for each processing stage
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Detected:</span>
              <span>{ps?.detected_at ? new Date(ps.detected_at).toLocaleString() : "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Queued:</span>
              <span>{ps?.queued_at ? new Date(ps.queued_at).toLocaleString() : "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Started:</span>
              <span>{ps?.started_at ? new Date(ps.started_at).toLocaleString() : "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Completed:</span>
              <span>{ps?.completed_at ? new Date(ps.completed_at).toLocaleString() : "—"}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
