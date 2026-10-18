"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./api";
import { useToast } from "@/components/ui/toast";

const poll = { refetchOnWindowFocus: true, staleTime: 4000 };

export const useAppState = () =>
  useQuery({ queryKey: ["state"], queryFn: async () => unwrap(await api.GET("/state")), refetchInterval: 12000, ...poll });
export const useToday = () => useQuery({ queryKey: ["today"], queryFn: async () => unwrap(await api.GET("/today")), ...poll });
export const useForecast = () => useQuery({ queryKey: ["forecast"], queryFn: async () => unwrap(await api.GET("/forecast")), ...poll });
export const usePayments = () => useQuery({ queryKey: ["payments"], queryFn: async () => unwrap(await api.GET("/payments")), ...poll });
export const useCollections = () => useQuery({ queryKey: ["collections"], queryFn: async () => unwrap(await api.GET("/collections")), ...poll });
export const useCash = () => useQuery({ queryKey: ["cash"], queryFn: async () => unwrap(await api.GET("/cash")), ...poll });
export const usePolicy = () => useQuery({ queryKey: ["policy"], queryFn: async () => unwrap(await api.GET("/policy")), ...poll });
export const useAgents = () => useQuery({ queryKey: ["agents"], queryFn: async () => unwrap(await api.GET("/agents")), ...poll });
export const useDecision = (id: string | null) =>
  useQuery({
    queryKey: ["decision", id],
    enabled: !!id,
    queryFn: async () => unwrap(await api.GET("/decisions/{proposal_id}", { params: { path: { proposal_id: id! } } })),
    ...poll,
  });

/** Run an action that changes the world, then refresh every screen. */
export function useAct<T = void>(fn: (arg: T) => Promise<{ message?: string } | void>, opts?: { ok?: string; tone?: "ok" | "info" | "warn" }) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: fn,
    onSuccess: async (r) => {
      await qc.invalidateQueries();
      const msg = (r && "message" in r && r.message) || opts?.ok;
      if (msg) toast({ title: msg, tone: opts?.tone ?? "ok" });
    },
    onError: (e: Error) => toast({ title: "That did not work", body: e.message, tone: "warn" }),
  });
}
