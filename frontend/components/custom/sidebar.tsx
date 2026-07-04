"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { api, clearToken } from "@/lib/api";
import type { GitHubConnection, User } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { 
  LayoutDashboard, 
  GitBranch, 
  Plus,
  Github,
  LogOut,
  ChevronDown,
  ChevronRight,
  User as UserIcon,
  Settings
} from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();
  const [connections, setConnections] = useState<GitHubConnection[]>([]);
  const [showConnections, setShowConnections] = useState(false);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [userLoading, setUserLoading] = useState(true);

  useEffect(() => {
    loadConnections();
    loadUser();
  }, []);

  const loadConnections = async () => {
    try {
      const conns = await api.listGitHubConnections();
      setConnections(conns);
    } catch (error) {
      console.error("Failed to load GitHub connections:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadUser = async () => {
    try {
      const userData = await api.me();
      setUser(userData);
    } catch (error) {
      console.error("Failed to load user:", error);
    } finally {
      setUserLoading(false);
    }
  };

  const handleConnectGitHub = async () => {
    try {
      const { authorization_url } = await api.getGitHubAuthUrl();
      window.location.href = authorization_url;
    } catch (error) {
      console.error("Failed to get GitHub auth URL:", error);
    }
  };

  const handleDeleteConnection = async (connectionId: number) => {
    try {
      await api.deleteGitHubConnection(connectionId);
      setConnections(connections.filter(c => c.id !== connectionId));
    } catch (error) {
      console.error("Failed to delete connection:", error);
    }
  };

  const handleLogout = () => {
    clearToken();
    window.location.href = "/login";
  };

  const navItems = [
    { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
    { href: "/agents", icon: GitBranch, label: "Agents" },
  ];

  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <aside className="w-64 border-r bg-card h-screen flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b">
        <Link href="/dashboard" className="flex items-center gap-2 font-bold text-xl">
          <GitBranch className="h-6 w-6 text-primary" />
          <span className="bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
            PR Guardian
          </span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                    isActive(item.href)
                      ? "bg-primary text-primary-foreground font-medium shadow-sm"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>

        {/* GitHub Connections */}
        <div className="mt-8">
          <button
            onClick={() => setShowConnections(!showConnections)}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg w-full transition-colors"
          >
            {showConnections ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            <Github className="h-4 w-4" />
            GitHub Accounts
            <span className="ml-auto text-xs bg-muted-foreground/20 px-2 py-0.5 rounded-full">
              {connections.length}
            </span>
          </button>

          {showConnections && (
            <div className="mt-2 space-y-2 pl-2">
              {loading ? (
                <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
                  Loading...
                </div>
              ) : connections.length === 0 ? (
                <Button
                  onClick={handleConnectGitHub}
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Connect Account
                </Button>
              ) : (
                <>
                  {connections.map((conn) => (
                    <div
                      key={conn.id}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-muted/50 hover:bg-muted transition-colors group"
                    >
                      <div className="flex items-center gap-2">
                        <Github className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium text-sm">{conn.github_username}</span>
                      </div>
                      <button
                        onClick={() => handleDeleteConnection(conn.id)}
                        className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all"
                        title="Disconnect"
                      >
                        <LogOut className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                  <Button
                    onClick={handleConnectGitHub}
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start text-muted-foreground hover:text-foreground"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add Another Account
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </nav>

      {/* User Profile */}
      <div className="p-4 border-t bg-muted/30">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center">
            <UserIcon className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            {userLoading ? (
              <div className="h-4 w-24 bg-muted animate-pulse rounded" />
            ) : user ? (
              <p className="text-sm font-medium truncate">{user.email}</p>
            ) : (
              <p className="text-sm text-muted-foreground">Not logged in</p>
            )}
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-muted-foreground hover:text-destructive hover:bg-destructive/10"
          onClick={handleLogout}
        >
          <LogOut className="h-4 w-4 mr-2" />
          Sign Out
        </Button>
      </div>
    </aside>
  );
}
