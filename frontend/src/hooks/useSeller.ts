import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { OrderStatus, SellerMove } from "@/types";
import * as api from "@/api/seller";
import { USE_MOCK } from "@/api/config";

export const useSellerDashboard = (days: number) =>
  useQuery({ queryKey: ["seller", "dashboard", days], queryFn: () => api.getDashboard(days), enabled: !USE_MOCK });

export const useSellerOrders = (status?: OrderStatus) =>
  useQuery({ queryKey: ["seller", "orders", status ?? "all"], queryFn: () => api.listSellerOrders(status), enabled: !USE_MOCK });

export function useAdvanceOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: number; to: SellerMove }) => api.advanceOrder(v.id, v.to),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["seller"] }),
  });
}
