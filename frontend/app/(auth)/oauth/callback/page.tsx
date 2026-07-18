"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, setToken } from "@/lib/api";

function OAuthCallback() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function handleCallback() {
      const code = searchParams.get("code");
      const provider = searchParams.get("provider") || "github";

      if (!code) {
        setError("No authorization code provided");
        setLoading(false);
        return;
      }

      try {
        const response = await api.handleOAuthCallback(provider as "github" | "google", code);
        setToken(response.access_token);
        router.push("/dashboard");
      } catch (err) {
        setError(err instanceof Error ? err.message : "OAuth callback failed");
        setLoading(false);
      }
    }

    handleCallback();
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
        <div className="w-full max-w-md space-y-4">
          <div className="rounded-md bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
          <button
            onClick={() => router.push("/login")}
            className="w-full rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
          >
            Back to login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <div className="text-muted-foreground">Completing sign in...</div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
          <div className="text-muted-foreground">Loading...</div>
        </div>
      }
    >
      <OAuthCallback />
    </Suspense>
  );
}
