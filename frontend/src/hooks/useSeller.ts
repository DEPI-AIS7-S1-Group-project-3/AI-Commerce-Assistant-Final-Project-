import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { OrderStatus, SellerMove, SellerProductFilter, SellerProductPatch } from "@/types";
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

export const useSellerProducts = (filter: SellerProductFilter, q: string) =>
  useQuery({ queryKey: ["seller", "products", filter, q], queryFn: () => api.listSellerProducts(filter, q), enabled: !USE_MOCK });

// After a change: refresh the seller lists/dashboard and the public catalog (price/stock/visibility).
export function useUpdateSellerProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: number; patch: SellerProductPatch }) => api.updateSellerProduct(v.id, v.patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["seller"] });
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: ["product"] });
    },
  });
}
