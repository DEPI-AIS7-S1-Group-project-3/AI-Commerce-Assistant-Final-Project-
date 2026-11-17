import { useQuery } from "@tanstack/react-query";
import { getPolicy, listPolicies } from "@/api/policies";

export const usePolicies = () => useQuery({ queryKey: ["policies"], queryFn: listPolicies, staleTime: Infinity });

export const usePolicy = (slug: string) =>
  useQuery({ queryKey: ["policy", slug], queryFn: () => getPolicy(slug), staleTime: Infinity });
