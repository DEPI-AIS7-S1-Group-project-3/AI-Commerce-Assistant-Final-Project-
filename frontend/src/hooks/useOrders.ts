import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReturnReason } from "@/types";
import * as api from "@/api/orders";
import { USE_MOCK } from "@/api/config";

export const useOrders = () => useQuery({ queryKey: ["orders"], queryFn: api.listOrders, enabled: !USE_MOCK });

export const useOrder = (id: number) =>
  useQuery({ queryKey: ["order", id], queryFn: () => api.getOrder(id), enabled: !USE_MOCK && id > 0 });

// After cancel/return: refresh this order, the list, and the catalog (cancel puts stock back).
export function useOrderActions(orderId: number) {
  const qc = useQueryClient();
  const done = () => {
    qc.invalidateQueries({ queryKey: ["order", orderId] });
    qc.invalidateQueries({ queryKey: ["orders"] });
    qc.invalidateQueries({ queryKey: ["products"] });
    qc.invalidateQueries({ queryKey: ["product"] });
  };
  return {
    cancel: useMutation({ mutationFn: () => api.cancelOrder(orderId), onSuccess: done }),
    requestReturn: useMutation({
      mutationFn: (v: { itemId: number; reason: ReturnReason; text: string | null }) =>
        api.requestReturn(orderId, v.itemId, v.reason, v.text),
      onSuccess: done,
    }),
  };
}
