"use client";

import Link from "next/link";
import {
  ShieldCheck,
  Bot,
  Zap,
  GitPullRequest,
  Braces,
  Lock,
  KeyRound,
  ScanEye,
  Sparkles,
  ArrowRight,
  Github,
  Moon,
  Sun,
  Check,
} from "lucide-react";
import { useTheme } from "@/components/custom/theme-provider";

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const isDark = theme === "dark";
  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      title="Toggle theme"
      aria-label="Toggle theme"
    >
      <Sun className="h-4 w-4 dark:hidden" />
      <Moon className="hidden h-4 w-4 dark:block" />
    </button>
  );
}

const FEATURES = [
  {
    icon: ScanEye,
    title: "Prompt-injection defense",
    body: "OWASP LLM01 detection with a curated pattern library plus an LLM judge. Encoded payloads are decoded and re-scanned before they ever reach your reviewers.",
  },
  {
    icon: ShieldCheck,
    title: "Malicious-code scanning",
    body: "High-signal static rules auto-decline real malware; dual-use patterns are handed to the model for context-aware judgment — not blind rejection.",
  },
  {
    icon: Bot,
    title: "Spam & low-effort filter",
    body: "Heuristics plus repo-aware scoring reject drive-by and bot PRs, with the bar lowered automatically for repeatedly-flagged accounts.",
  },
  {
    icon: Sparkles,
    title: "RAG-powered summaries",
    body: "Each agent ingests your repo and issues, then rewrites accepted PRs with a conventional-commit title and a structured, reviewer-ready description.",
  },
  {
    icon: KeyRound,
    title: "Bring your own key",
    body: "Groq, Gemini, or a local Ollama server — pick your provider and drop in your own API key. No key? It falls back to the server default.",
  },
  {
    icon: Lock,
    title: "Free & self-hostable",
    body: "Runs on CPU with local embeddings — no GPU, no paid embedding API. Deploy the whole stack for free, or on a small VPS with one command.",
  },
];

const PIPELINE = [
  { n: "01", label: "Prompt injection", icon: ScanEye },
  { n: "02", label: "Spam & quality", icon: Bot },
  { n: "03", label: "Malicious code", icon: ShieldCheck },
  { n: "04", label: "Summarize & approve", icon: Sparkles },
];

const PROVIDERS = ["Groq", "Google Gemini", "Ollama", "GitHub"];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Nav */}
      <header className="sticky top-0 z-50 border-b border-border/60 glass">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2 font-bold">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <span className="text-lg tracking-tight">PR Guardian</span>
          </Link>
          <nav className="hidden items-center gap-8 text-sm text-muted-foreground md:flex">
            <a href="#features" className="transition-colors hover:text-foreground">Features</a>
            <a href="#pipeline" className="transition-colors hover:text-foreground">Pipeline</a>
            <a href="#providers" className="transition-colors hover:text-foreground">Providers</a>
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link
              href="/login"
              className="hidden rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground sm:inline-block"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-90"
            >
              Get started
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-grid [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[500px] glow-primary" />
        <div className="relative mx-auto max-w-4xl px-6 pb-24 pt-24 text-center sm:pt-32">
          <div className="animate-fade-up inline-flex items-center gap-2 rounded-full border border-border bg-card/50 px-3 py-1 text-xs font-medium text-muted-foreground">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
            </span>
            Autonomous PR review, before a human looks
          </div>
          <h1 className="animate-fade-up mt-6 text-4xl font-bold tracking-tight sm:text-6xl">
            The AI guardian for your
            <br className="hidden sm:block" />{" "}
            <span className="text-gradient">GitHub pull requests</span>
          </h1>
          <p className="animate-fade-up mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            PR Guardian learns your repository, then screens every incoming PR through a
            four-layer security pipeline — blocking prompt injection, malicious code, and
            spam, and rewriting the good ones into clean, reviewer-ready descriptions.
          </p>
          <div className="animate-fade-up mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/signup"
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition-all hover:opacity-90 sm:w-auto"
            >
              Start guarding your repos
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/login"
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-card px-6 py-3 text-sm font-semibold transition-colors hover:bg-muted sm:w-auto"
            >
              <Github className="h-4 w-4" />
              Sign in
            </Link>
          </div>
          <p className="animate-fade-up mt-4 text-xs text-muted-foreground">
            Free to self-host · Runs on CPU · Bring your own API key
          </p>
        </div>
      </section>

      {/* Provider strip */}
      <section id="providers" className="border-y border-border/60 bg-muted/30">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <p className="text-center text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Works with the models you already use
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
            {PROVIDERS.map((p) => (
              <span key={p} className="text-lg font-semibold text-muted-foreground/70">
                {p}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl px-6 py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            A full review team, in one agent
          </h2>
          <p className="mt-4 text-muted-foreground">
            Every layer runs automatically on each PR. Threats are declined and the author is
            flagged; legitimate work is polished and approved.
          </p>
        </div>
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5"
            >
              <div className="grid h-11 w-11 place-items-center rounded-xl bg-accent text-accent-foreground transition-transform group-hover:scale-105">
                <f.icon className="h-5 w-5" />
              </div>
              <h3 className="mt-5 font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section id="pipeline" className="border-y border-border/60 bg-muted/30">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              A strict, sequential gate
            </h2>
            <p className="mt-4 text-muted-foreground">
              A PR that fails any layer never reaches the next. Only clean PRs make it to
              summary and approval.
            </p>
          </div>
          <div className="mt-14 grid gap-4 md:grid-cols-4">
            {PIPELINE.map((step, i) => (
              <div key={step.n} className="relative">
                <div className="rounded-2xl border border-border bg-card p-6">
                  <div className="flex items-center justify-between">
                    <span className="grid h-10 w-10 place-items-center rounded-lg bg-primary/10 text-primary">
                      <step.icon className="h-5 w-5" />
                    </span>
                    <span className="font-mono text-sm text-muted-foreground">{step.n}</span>
                  </div>
                  <p className="mt-4 font-semibold">{step.label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {i < 3 ? "Fail → decline + flag" : "Pass → rewrite + approve"}
                  </p>
                </div>
                {i < PIPELINE.length - 1 && (
                  <ArrowRight className="absolute -right-3 top-1/2 hidden h-5 w-5 -translate-y-1/2 text-muted-foreground/40 md:block" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* BYO key highlight */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
              <KeyRound className="h-3.5 w-3.5" /> Your keys, your control
            </div>
            <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
              Any provider. Zero lock-in.
            </h2>
            <p className="mt-4 text-muted-foreground">
              Choose Groq for speed, Gemini for reach, or point at a local Ollama server for
              full privacy. Store your own key in settings — encrypted at rest — or run on the
              server default. Embeddings run locally on CPU, so retrieval is free either way.
            </p>
            <ul className="mt-6 space-y-3">
              {[
                "Per-account provider + API key",
                "Local CPU embeddings — no GPU, no embedding bills",
                "Falls back to a shared default when you have no key",
              ].map((t) => (
                <li key={t} className="flex items-start gap-3 text-sm">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-success/15 text-success">
                    <Check className="h-3.5 w-3.5" />
                  </span>
                  {t}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-border bg-card p-2 shadow-xl shadow-primary/5">
            <div className="rounded-xl bg-muted/50 p-5 font-mono text-sm">
              <div className="flex items-center gap-1.5 pb-4">
                <span className="h-3 w-3 rounded-full bg-destructive/60" />
                <span className="h-3 w-3 rounded-full bg-warning/60" />
                <span className="h-3 w-3 rounded-full bg-success/60" />
                <span className="ml-2 text-xs text-muted-foreground">settings › llm</span>
              </div>
              <div className="space-y-2 text-muted-foreground">
                <p><span className="text-primary">provider</span> = <span className="text-foreground">groq</span></p>
                <p><span className="text-primary">model</span> = <span className="text-foreground">llama-3.3-70b-versatile</span></p>
                <p><span className="text-primary">api_key</span> = <span className="text-foreground">••••••••••••••••</span></p>
                <p><span className="text-primary">embeddings</span> = <span className="text-foreground">bge-small (local, CPU)</span></p>
                <p className="pt-2 text-success">✓ saved · encrypted at rest</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="relative overflow-hidden rounded-3xl border border-border bg-card px-6 py-16 text-center">
          <div className="pointer-events-none absolute inset-0 glow-primary" />
          <div className="relative">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Put a guardian on every repo
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
              Connect GitHub, pick a repo, and let PR Guardian handle the first pass. Set up in
              minutes.
            </p>
            <Link
              href="/signup"
              className="mt-8 inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition-all hover:opacity-90"
            >
              Get started free
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 text-sm text-muted-foreground sm:flex-row">
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <ShieldCheck className="h-4 w-4 text-primary" />
            PR Guardian
          </div>
          <p>RAG-powered agentic GitHub PR management.</p>
          <div className="flex items-center gap-5">
            <Link href="/login" className="transition-colors hover:text-foreground">Sign in</Link>
            <Link href="/signup" className="transition-colors hover:text-foreground">Sign up</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
