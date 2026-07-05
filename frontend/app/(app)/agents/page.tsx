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
import type { Agent, GitHubConnection } from "@/lib/types";
import { GitBranch, Github, Plus } from "lucide-react";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [connections, setConnections] = useState<GitHubConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedGithubAccount, setSelectedGithubAccount] = useState<string>("");

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.listAgents(),
      api.listGitHubConnections(),
    ])
      .then(([a, c]) => {
        setAgents(a);
        setConnections(c);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredAgents = selectedGithubAccount
    ? agents.filter(a => a.github_installation_id === connections.find(c => c.github_username === selectedGithubAccount)?.id)
    : agents;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Agents</h1>
          <p className="text-muted-foreground">
            Manage your GitHub repository agents.
          </p>
        </div>
        <div className="flex gap-2">
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

      {!loading && filteredAgents.length === 0 && (
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

      {!loading && filteredAgents.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredAgents.map((agent) => (
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
                    <span>LLM</span>
                    <span className="font-medium text-foreground">
                      {agent.llm_provider}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Vector DB</span>
                    <span className="font-medium text-foreground">
                      {agent.vector_db_type}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Ingestion</span>
                    <span className="font-medium text-foreground capitalize">
                      {agent.ingestion_status}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Chunks</span>
                    <span className="font-medium text-foreground">
                      {agent.chunk_count}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
