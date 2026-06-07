import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { supabase } from "../lib/supabase";
import type { Session as SupabaseSession } from "@supabase/supabase-js";

interface AuthUser {
  id: string;
  email?: string;
  username?: string;
}

interface AuthContextType {
  user: AuthUser | null;
  session: SupabaseSession | null;
  loading: boolean;
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => ReturnType<typeof supabase.auth.signInWithPassword>;
  signUp: (email: string, password: string, username: string) => ReturnType<typeof supabase.auth.signUp>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [session, setSession] = useState<SupabaseSession | null>(null);
  const [loading, setLoading] = useState(true);
  const initialisedRef = useRef(false);

  const clearAuth = useCallback(() => {
    setUser(null);
    setSession(null);
  }, []);

  useEffect(() => {
    if (initialisedRef.current) return;
    initialisedRef.current = true;

    async function initAuth() {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        setSession(session);
        setUser(
          session?.user
            ? {
                id: session.user.id,
                email: session.user.email ?? undefined,
                username: session.user.user_metadata?.["username"] ?? undefined,
              }
            : null,
        );
      } catch (error) {
        console.error("Error getting session:", error);
      } finally {
        setLoading(false);
      }
    }

    initAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setUser(
        session?.user
          ? {
              id: session.user.id,
              email: session.user.email ?? undefined,
              username: session.user.user_metadata?.["username"] ?? undefined,
            }
          : null,
      );
    });

    const handleForceLogout = () => {
      clearAuth();
      supabase.auth.signOut().catch(() => {});
    };

    window.addEventListener('auth:logout', handleForceLogout);

    return () => {
      subscription.unsubscribe();
      window.removeEventListener('auth:logout', handleForceLogout);
    };
  }, [clearAuth]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const result = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (result.error) {
        throw new Error(result.error.message);
      }

      return result;
    },
    [],
  );

  const signUp = useCallback(
    async (email: string, password: string, username: string) => {
      const result = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            username,
          },
        },
      });

      if (result.error) {
        throw new Error(result.error.message);
      }

      return result;
    },
    [],
  );

  const signOut = useCallback(async () => {
    const { error } = await supabase.auth.signOut();
    if (error) {
      console.error("Error signing out:", error);
    }
    setUser(null);
    setSession(null);
  }, []);

  const value: AuthContextType = {
    user,
    session,
    loading,
    isAuthenticated: !!session,
    signIn,
    signUp,
    signOut,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export default AuthContext;
