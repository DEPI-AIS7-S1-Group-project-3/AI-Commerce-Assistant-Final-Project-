import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/lib/i18n";

// Wrap pages that need login (checkout, orders, addresses):
//   <Route path="checkout" element={<RequireAuth><CheckoutPage /></RequireAuth>} />
// Logged-out users go to /login and come back here after logging in.
export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  const { t } = useI18n();
  if (loading) return <p className="text-ink-soft">{t("cart.loading")}...</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}
