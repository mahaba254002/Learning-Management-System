import { createContext, useEffect, useState, useCallback } from "react";
import { apiRequest, setWorkspaceAccess } from "../api/client";
import { useQueryClient } from '@tanstack/react-query';
import SessionRecovery from '../components/common/SessionRecovery';

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [workspace, setWorkspace] = useState(null);
  const [isWorkspaceChanging, setIsWorkspaceChanging] = useState(false);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [actor, setActor] = useState(null);

  useEffect(() => {
    const expired = () => setSessionEnded(true);
    window.addEventListener('skynet:session-ended', expired);
    return () => window.removeEventListener('skynet:session-ended', expired);
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function check() {
      try {
        const data = await apiRequest("/api/me");
        if (isMounted) { setUser(data); setActor(data); }
      } catch {
        if (isMounted) setUser(null);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    check();

    return () => {
      isMounted = false;
    };
  }, []);

  // loginPath lets callers choose the staff or student door while sharing
  // this one method — the actual portal enforcement happens server-side
  // (see backend/app/api/routes/auth.py), this parameter only decides
  // which URL the frontend calls.
  const login = useCallback(async (email, password, loginPath = "/api/auth/login", rememberMe = false) => {
    const data = await apiRequest(loginPath, {
      method: "POST",
      body: { ...(loginPath === "/api/auth/student/login" && !email.includes("@") ? { student_id: email } : { email }), password, remember_me: rememberMe },
      workspace: false,
    });
    await queryClient.cancelQueries();
    setWorkspaceAccess(null);
    setWorkspace(null);
    queryClient.clear();
    setUser({ ...data.user, must_change_password: data.must_change_password });
    setActor(data.user); setSessionEnded(false);
    return data;
  }, [queryClient]);

  const logout = useCallback(async () => {
    try {
      await apiRequest("/api/auth/logout", { method: "POST", workspace: false });
    } finally {
      await queryClient.cancelQueries();
      setWorkspaceAccess(null);
      setWorkspace(null);
      queryClient.clear();
      setUser(null);
      setActor(null); setSessionEnded(false);
    }
  }, [queryClient]);

  const startWorkspace = useCallback(async (targetUserId) => {
    setIsWorkspaceChanging(true);
    try {
      const data = await apiRequest("/api/workspace-access/start", { method: "POST", body: { target_user_id: targetUserId } });
      await queryClient.cancelQueries();
      setWorkspaceAccess(data);
      queryClient.clear();
      setWorkspace(data);
      setUser(data.user);
      return data.user;
    } finally {
      setIsWorkspaceChanging(false);
    }
  }, [queryClient]);

  const stopWorkspace = useCallback(async () => {
    setIsWorkspaceChanging(true);
    try {
      try {
        await apiRequest("/api/workspace-access/stop", { method: "POST" });
      } catch {
        // An expired/revoked target must never prevent returning to the real session.
      }
      await queryClient.cancelQueries();
      setWorkspaceAccess(null);
      queryClient.clear();
      setWorkspace(null);
      try {
        const actor = await apiRequest("/api/me", { workspace: false });
        setUser(actor);
        return actor;
      } catch {
        setUser(null);
        return null;
      }
    } finally {
      setIsWorkspaceChanging(false);
    }
  }, [queryClient]);

  const changePassword = useCallback(async (values) => {
    await apiRequest("/api/auth/change-password", { method: "POST", body: values });
    // The server invalidates this session when the password changes.
    queryClient.clear();
    setUser(null);
  }, [queryClient]);

  const value = {
    user,
    isLoading,
    isAuthenticated: user !== null,
    login,
    logout,
    changePassword,
    workspace,
    readOnly: Boolean(workspace?.read_only),
    isWorkspaceChanging,
    startWorkspace,
    stopWorkspace,
  };

  return <AuthContext.Provider value={value}>{children}{sessionEnded && user && <SessionRecovery user={actor || user}
    onRecovered={recovered => { setActor(recovered); if (!workspace) setUser(recovered); setSessionEnded(false); window.dispatchEvent(new Event('skynet:session-restored')); }} onLogout={logout} />}</AuthContext.Provider>;
}
