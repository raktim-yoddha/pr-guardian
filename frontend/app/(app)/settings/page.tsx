"use client";

import { useEffect, useState } from "react";
import { KeyRound, Check, Loader2, Zap, Sparkles, Server } from "lucide-react";
import { api } from "@/lib/api";
import type { LlmProvider, UserSettings } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const PROVIDERS: {
  id: LlmProvider;
  name: string;
  icon: typeof Zap;
  blurb: string;
  keyLabel: string;
  keyLink?: string;
  needsKey: boolean;
}[] = [
  {
    id: "groq",
    name: "Groq",
    icon: Zap,
    blurb: "Fast, free inference. Recommended default.",
    keyLabel: "Groq API key",
    keyLink: "https://console.groq.com/keys",
    needsKey: true,
  },
  {
    id: "gemini",
    name: "Google Gemini",
    icon: Sparkles,
    blurb: "Google's Gemini Flash models.",
    keyLabel: "Gemini API key",
    keyLink: "https://aistudio.google.com/apikey",
    needsKey: true,
  },
  {
    id: "ollama",
    name: "Ollama",
    icon: Server,
    blurb: "Local models on your own server. No key needed.",
    keyLabel: "Ollama base URL",
    needsKey: false,
  },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [provider, setProvider] = useState<LlmProvider>("groq");
  const [keys, setKeys] = useState<Record<string, string>>({ groq: "", gemini: "" });
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const s = await api.getSettings();
        setSettings(s);
        setProvider((s.preferred_provider as LlmProvider) || (s.default_provider as LlmProvider) || "groq");
        setOllamaUrl(s.ollama_base_url || "");
      } catch (e: any) {
        setError(e?.message || "Failed to load settings");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const isConfigured = (id: string) => settings?.configured_providers.includes(id);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const api_keys: Partial<Record<LlmProvider, string>> = {};
      // Only send keys the user actually typed (non-empty).
      for (const p of ["groq", "gemini"] as const) {
        if (keys[p]?.trim()) api_keys[p] = keys[p].trim();
      }
      const updated = await api.updateSettings({
        preferred_provider: provider,
        ollama_base_url: provider === "ollama" ? ollamaUrl || null : undefined,
        api_keys: Object.keys(api_keys).length ? api_keys : undefined,
      });
      setSettings(updated);
      setKeys({ groq: "", gemini: "" }); // clear inputs; stored state shows via badges
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: any) {
      setError(e?.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose the LLM provider your agents use and bring your own API key.
        </p>
      </div>

      {/* Provider selection */}
      <section className="rounded-2xl border border-border bg-card p-6">
        <div className="flex items-center gap-2">
          <KeyRound className="h-5 w-5 text-primary" />
          <h2 className="font-semibold">LLM provider</h2>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Server default:{" "}
          <span className="font-medium text-foreground">{settings?.default_provider}</span>. Your
          selection overrides it for your agents.
        </p>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          {PROVIDERS.map((p) => {
            const active = provider === p.id;
            return (
              <button
                key={p.id}
                onClick={() => setProvider(p.id)}
                className={`rounded-xl border p-4 text-left transition-all ${
                  active
                    ? "border-primary bg-accent/50 ring-1 ring-primary"
                    : "border-border hover:border-primary/40 hover:bg-muted/50"
                }`}
              >
                <div className="flex items-center justify-between">
                  <p.icon className={`h-5 w-5 ${active ? "text-primary" : "text-muted-foreground"}`} />
                  {isConfigured(p.id) && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-[10px] font-medium text-success">
                      <Check className="h-3 w-3" /> key set
                    </span>
                  )}
                </div>
                <p className="mt-3 text-sm font-semibold">{p.name}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{p.blurb}</p>
              </button>
            );
          })}
        </div>

        {/* Key / URL input for the selected provider */}
        <div className="mt-6 space-y-4 border-t border-border pt-6">
          {PROVIDERS.filter((p) => p.id === provider).map((p) => (
            <div key={p.id}>
              <div className="flex items-center justify-between">
                <Label htmlFor="cred">{p.keyLabel}</Label>
                {p.keyLink && (
                  <a
                    href={p.keyLink}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-primary hover:underline"
                  >
                    Get a key →
                  </a>
                )}
              </div>
              {p.needsKey ? (
                <>
                  <Input
                    id="cred"
                    type="password"
                    autoComplete="off"
                    placeholder={
                      isConfigured(p.id) ? "•••••••• (saved — type to replace)" : "Paste your API key"
                    }
                    value={keys[p.id] ?? ""}
                    onChange={(e) => setKeys((k) => ({ ...k, [p.id]: e.target.value }))}
                    className="mt-2"
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    Stored encrypted. Leave blank to keep the current key
                    {isConfigured(p.id) ? "" : ", or fall back to the server default"}.
                  </p>
                </>
              ) : (
                <>
                  <Input
                    id="cred"
                    type="text"
                    placeholder="http://localhost:11434"
                    value={ollamaUrl}
                    onChange={(e) => setOllamaUrl(e.target.value)}
                    className="mt-2"
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    URL of your Ollama server. Must be reachable from the backend.
                  </p>
                </>
              )}
            </div>
          ))}
        </div>

        {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

        <div className="mt-6 flex items-center gap-3">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Save settings
          </Button>
          {saved && (
            <span className="inline-flex items-center gap-1 text-sm text-success">
              <Check className="h-4 w-4" /> Saved
            </span>
          )}
        </div>
      </section>

      <p className="mt-6 text-xs text-muted-foreground">
        Embeddings run locally on CPU (bge-small) — no key required. If no provider key is set
        anywhere, agents use the server&apos;s default provider.
      </p>
    </div>
  );
}
