import { useQuery } from "@tanstack/react-query";
import { getProductReviews } from "@/api/reviews";

export const useProductReviews = (productId: number) =>
  useQuery({ queryKey: ["reviews", productId], queryFn: () => getProductReviews(productId), enabled: productId > 0 });
