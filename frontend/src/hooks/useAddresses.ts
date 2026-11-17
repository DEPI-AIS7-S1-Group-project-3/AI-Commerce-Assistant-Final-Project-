import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AddressInput } from "@/types";
import * as api from "@/api/addresses";
import { USE_MOCK } from "@/api/config";

const KEY = ["addresses"];

export const useAddresses = () => useQuery({ queryKey: KEY, queryFn: api.listAddresses, enabled: !USE_MOCK });

export function useAddressMutations() {
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: KEY });
  return {
    create: useMutation({ mutationFn: (d: AddressInput) => api.createAddress(d), onSuccess: done }),
    update: useMutation({ mutationFn: ({ id, d }: { id: number; d: AddressInput }) => api.updateAddress(id, d), onSuccess: done }),
    makeDefault: useMutation({ mutationFn: (id: number) => api.makeDefault(id), onSuccess: done }),
    remove: useMutation({ mutationFn: (id: number) => api.deleteAddress(id), onSuccess: done }),
  };
}
