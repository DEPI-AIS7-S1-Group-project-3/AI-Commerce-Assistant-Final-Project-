// Same rule as the backend (services/checkout.py): flat fee per seller order,
// free when that seller's subtotal reaches the threshold. Delivery in 3 days.
export const SHIPPING_FEE = 60;
export const FREE_FROM = 5000;

export const shippingFor = (sellerSubtotal: number) => (sellerSubtotal >= FREE_FROM ? 0 : SHIPPING_FEE);
