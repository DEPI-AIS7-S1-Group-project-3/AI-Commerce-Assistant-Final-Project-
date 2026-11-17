import type { Policy, PolicySummary } from "@/types";
import { ApiError, http } from "./config";

// Public: no login needed. Policies always come from the backend (no mock copy).
export const listPolicies = () => http<PolicySummary[]>("/policies");

export async function getPolicy(slug: string): Promise<Policy | null> {
  try {
    return await http<Policy>(`/policies/${encodeURIComponent(slug)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}
