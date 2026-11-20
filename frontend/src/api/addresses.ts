import type { Address, AddressInput } from "@/types";
import { getToken } from "@/hooks/useAuth";
import { http } from "./config";

// Backend /addresses (login required). Default address comes first.
const auth = () => ({ Authorization: `Bearer ${getToken() ?? ""}` });

export const listAddresses = () => http<Address[]>("/addresses", { headers: auth() });

export const createAddress = (data: AddressInput) =>
  http<Address>("/addresses", { method: "POST", headers: auth(), body: JSON.stringify(data) });

export const updateAddress = (id: number, data: AddressInput) =>
  http<Address>(`/addresses/${id}`, { method: "PUT", headers: auth(), body: JSON.stringify(data) });

export const makeDefault = (id: number) =>
  http<Address>(`/addresses/${id}/default`, { method: "POST", headers: auth() });

export const deleteAddress = (id: number) => http<void>(`/addresses/${id}`, { method: "DELETE", headers: auth() });
