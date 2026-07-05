"use client";

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
import type { FlaggedAccount, GitHubConnection } from "@/lib/types";
import { Shield, Github, AlertTriangle } from "lucide-react";

export default function FlaggedPage() {
  const [flagged, setFlagged] = useState<FlaggedAccount[]>([]);
  const [connections, setConnections] = useState<GitHubConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unflagging, setUnflagging] = useState<string | null>(null);
  const [selectedGithubAccount, setSelectedGithubAccount] = useState<string>("");

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.listFlaggedAccounts(),
      api.listGitHubConnections(),
    ])
      .then(([f, c]) => {
        setFlagged(f);
        setConnections(c);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

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

  const filteredFlagged = selectedGithubAccount
    ? flagged.filter(f => f.github_username === selectedGithubAccount)
    : flagged;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Flagged Accounts</h1>
          <p className="text-muted-foreground">
            GitHub accounts flagged by your agents&apos; pipelines.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor="github-filter">Filter by GitHub Account:</Label>
          <Select value={selectedGithubAccount} onValueChange={setSelectedGithubAccount}>
            <SelectTrigger id="github-filter" className="w-[200px]">
              <SelectValue placeholder="All accounts" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All accounts</SelectItem>
              {connections.map((c) => (
                <SelectItem key={c.id} value={c.github_username}>
                  <div className="flex items-center gap-2">
                    <Github className="h-4 w-4" />
                    {c.github_username}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {loading && <p className="text-muted-foreground">Loading…</p>}
      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && filteredFlagged.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              No flagged accounts
            </CardTitle>
            <CardDescription>
              GitHub accounts flagged by your agents&apos; pipelines will appear here.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {!loading && filteredFlagged.length > 0 && (
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
                  {filteredFlagged.map((f) => (
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
          </CardContent>
        </Card>
      )}
    </div>
  );
}
