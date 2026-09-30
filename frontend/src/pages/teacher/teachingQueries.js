import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { useAuth } from "../../context/useAuth";

export function useTeachingQuery(path) {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["teaching", user.id, path],
    queryFn: () => apiRequest(path),
    enabled: Boolean(path),
    retry: false,
  });
}

export function useTeachingMutation() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ path, method = "POST", body }) => apiRequest(path, { method, body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["teaching", user.id] }),
  });
}
