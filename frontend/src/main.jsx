import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./context/AuthContext";
import App from "./App";
import { retryDelay, shouldRetry } from "./api/errors";
import "./styles/global.css";

// Retry only temporary failures (no connection, API starting up); never access or validation errors.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: shouldRetry, retryDelay, refetchOnReconnect: true },
    mutations: { retry: false },
  },
});

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>
);