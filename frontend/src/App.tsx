import { Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import HomePage from "@/pages/HomePage";
import ProductsPage from "@/pages/ProductsPage";
import AssistantPage from "@/pages/AssistantPage";
import NotFoundPage from "@/pages/NotFoundPage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import CartPage from "@/pages/CartPage";
import ProductPage from "@/pages/ProductPage";
import PolicyPage, { PoliciesIndex } from "@/pages/PolicyPage";
import CheckoutPage from "@/pages/CheckoutPage";
import AddressesPage from "@/pages/AddressesPage";
import OrderConfirmationPage from "@/pages/OrderConfirmationPage";
import OrdersPage from "@/pages/OrdersPage";
import OrderDetailPage from "@/pages/OrderDetailPage";
import RequireAuth from "@/components/RequireAuth";
import SellerDashboardPage from "@/pages/SellerDashboardPage";
import SellerOrdersPage from "@/pages/SellerOrdersPage";
import SellerProductsPage from "@/pages/SellerProductsPage";


export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="products/:id" element={<ProductPage />} />
        <Route path="policies" element={<PoliciesIndex />} />
        <Route path="policies/:slug" element={<PolicyPage />} />
        <Route path="assistant" element={<AssistantPage />} />
        {/* Next: seller product creation (stage C) */}
        <Route path="*" element={<NotFoundPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="cart" element={<CartPage />} />
        <Route path="checkout" element={<RequireAuth><CheckoutPage /></RequireAuth>} />
        <Route path="addresses" element={<RequireAuth><AddressesPage /></RequireAuth>} />
        <Route path="orders/confirmation" element={<RequireAuth><OrderConfirmationPage /></RequireAuth>} />
        <Route path="orders" element={<RequireAuth><OrdersPage /></RequireAuth>} />
        <Route path="orders/:id" element={<RequireAuth><OrderDetailPage /></RequireAuth>} />
        <Route path="seller" element={<RequireAuth role="seller"><SellerDashboardPage /></RequireAuth>} />
        <Route path="seller/orders" element={<RequireAuth role="seller"><SellerOrdersPage /></RequireAuth>} />
        <Route path="seller/products" element={<RequireAuth role="seller"><SellerProductsPage /></RequireAuth>} />
      </Route>
    </Routes>
  );
}