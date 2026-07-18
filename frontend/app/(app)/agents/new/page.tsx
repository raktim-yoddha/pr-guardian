"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, api } from "@/lib/api";
import type { LlmProvider, VectorDbType, GitHubConnection, GitHubRepo } from "@/lib/types";
import { Github, AlertCircle } from "lucide-react";

export default function NewAgentPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [selectedRepo, setSelectedRepo] = useState("");
  const [llm, setLlm] = useState<LlmProvider>("groq");
  const [vectorDb, setVectorDb] = useState<VectorDbType>("pgvector");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [connections, setConnections] = useState<GitHubConnection[]>([]);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(false);

  useEffect(() => {
    loadConnections();
  }, []);

  const loadConnections = async () => {
    try {
      const conns = await api.listGitHubConnections();
      setConnections(conns);
    } catch (error) {
      console.error("Failed to load GitHub connections:", error);
    }
  };

  const loadRepos = async (connectionId: number) => {
    setLoadingRepos(true);
    try {
      const repoList = await api.listGitHubRepos(connectionId);
      setRepos(repoList);
    } catch (error) {
      console.error("Failed to load repos:", error);
      setRepos([]);
    } finally {
      setLoadingRepos(false);
    }
  };

  const handleConnectionChange = (connectionId: string) => {
    const id = parseInt(connectionId);
    setSelectedConnection(id);
    setSelectedRepo("");
    if (id) {
      loadRepos(id);
    } else {
      setRepos([]);
    }
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const agent = await api.createAgent({
        name: name.trim(),
        repo_full_name: selectedRepo.trim(),
        llm_provider: llm,
        vector_db_type: vectorDb,
        github_installation_id: selectedConnection,
      });
      router.push(`/agents/${agent.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create agent");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Create agent</h1>
        <p className="text-muted-foreground">
          Point a guardbot at a GitHub repository.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Agent details</CardTitle>
          <CardDescription>
            Select a connected GitHub account and choose a repository to monitor.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}
            
            {connections.length === 0 ? (
              <div className="rounded-md border border-warning/30 bg-warning/10 p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="mt-0.5 h-5 w-5 text-warning" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-foreground">
                      No GitHub accounts connected
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Connect a GitHub account from the sidebar to create an agent.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="name">Agent name</Label>
                  <Input
                    id="name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Backend Guardian"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="connection">GitHub Account</Label>
                  <Select
                    value={selectedConnection?.toString() || ""}
                    onValueChange={handleConnectionChange}
                  >
                    <SelectTrigger id="connection">
                      <SelectValue placeholder="Select a connected account" />
                    </SelectTrigger>
                    <SelectContent>
                      {connections.map((conn) => (
                        <SelectItem key={conn.id} value={conn.id.toString()}>
                          <div className="flex items-center gap-2">
                            <Github className="h-4 w-4" />
                            {conn.github_username}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="repo">Repository</Label>
                  <Select
                    value={selectedRepo}
                    onValueChange={setSelectedRepo}
                    disabled={!selectedConnection || loadingRepos}
                  >
                    <SelectTrigger id="repo">
                      <SelectValue placeholder={
                        !selectedConnection 
                          ? "Select an account first" 
                          : loadingRepos 
                          ? "Loading repositories..." 
                          : "Select a repository"
                      } />
                    </SelectTrigger>
                    <SelectContent>
                      {repos.map((repo) => (
                        <SelectItem key={repo.full_name} value={repo.full_name}>
                          <div className="flex items-center gap-2">
                            <Github className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium">{repo.full_name}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>LLM provider</Label>
                    <Select
                      value={llm}
                      onValueChange={(v) => setLlm(v as LlmProvider)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="groq">Groq (fast, free)</SelectItem>
                        <SelectItem value="gemini">Gemini Flash</SelectItem>
                        <SelectItem value="ollama">Ollama (local)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Vector DB</Label>
                    <Select
                      value={vectorDb}
                      onValueChange={(v) => setVectorDb(v as VectorDbType)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select vector DB" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="pgvector">pgvector</SelectItem>
                        <SelectItem value="chromadb">ChromaDB</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </>
            )}
          </CardContent>
          <div className="flex items-center justify-end gap-3 p-6 pt-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.back()}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading || connections.length === 0 || !selectedRepo}>
              {loading ? "Creating…" : "Create agent"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
