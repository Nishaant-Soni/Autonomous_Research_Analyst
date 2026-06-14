import React, { createContext, useContext, useEffect, useState } from "react";
import { setAuthFailureCallback } from "../lib/authFetch";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface User {
  id: number;
  email: string;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Register callback so authFetch can clear user on double-401.
    setAuthFailureCallback(() => setUser(null));

    // Rehydrate auth state from httpOnly cookie without re-prompting the user.
    fetch(`${API_URL}/auth/me`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { user_id: number; email: string } | null) => {
        if (data) setUser({ id: data.user_id, email: data.email });
      })
      .catch(() => {
        // Network error — treat as unauthenticated; user can log in.
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string): Promise<void> {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string };
      throw new Error(body.detail ?? "Login failed");
    }
    const data = await res.json() as { user_id: number; email: string };
    setUser({ id: data.user_id, email: data.email });
  }

  async function logout(): Promise<void> {
    await fetch(`${API_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => {});
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
