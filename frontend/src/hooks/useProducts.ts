import { useQuery } from "@tanstack/react-query";
import { getProduct, listBrands, listCategories, listProducts } from "@/api/products";
import type { ProductQuery } from "@/types";

export const useProducts = (query: ProductQuery) =>
  useQuery({ queryKey: ["products", query], queryFn: () => listProducts(query) });

export const useProduct = (id: number) =>
  useQuery({ queryKey: ["product", id], queryFn: () => getProduct(id), enabled: id > 0 });

export const useCategories = () =>
  useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });

export const useBrands = () =>
  useQuery({ queryKey: ["brands"], queryFn: listBrands, staleTime: Infinity });
