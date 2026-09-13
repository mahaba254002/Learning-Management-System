import { createContext, useEffect, useState, useCallback } from "react";
import { apiRequest } from "../api/client";

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function check() {
      try {
        const data = await apiRequest("/api/me");
        if (isMounted) setUser(data);
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

  const login = useCallback(async (username, password) => {
    const data = await apiRequest("/api/auth/login", {
      method: "POST",
      body: { username, password },
    });
    setUser(data.user);
    return data;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } finally {
      setUser(null);
    }
  }, []);

  const value = {
    user,
    isLoading,
    isAuthenticated: user !== null,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}