from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import AppError, NotFoundError
from ai_commerce_marketplace.database.models.cart import Cart, CartItem
from ai_commerce_marketplace.database.models.catalog import Product
from ai_commerce_marketplace.schemas.cart import CartItemOut, CartOut


def _get_or_create_cart(session: Session, user_id: int) -> Cart:
    cart = session.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        cart = Cart(user_id=user_id)
        session.add(cart)
        session.flush()
    return cart


def _active_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None or not product.is_active:
        raise NotFoundError("Product not found", code="product_not_found")
    return product


def _check_stock(product: Product, qty: int) -> None:
    if qty > product.stock_qty:
        raise AppError(
            "Requested quantity exceeds available stock",
            code="insufficient_stock",
            details={"product_id": product.id, "available": product.stock_qty},
        )


def _find_item(session: Session, cart_id: int, product_id: int) -> CartItem | None:
    stmt = select(CartItem).where(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
    return session.scalar(stmt)


def view_cart(session: Session, user_id: int) -> CartOut:
    cart = session.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        return CartOut(items=[], subtotal_egp=Decimal("0.00"))
    stmt = (
        select(CartItem, Product)
        .join(Product, Product.id == CartItem.product_id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.id)
    )
    items: list[CartItemOut] = []
    subtotal = Decimal("0.00")
    for item, product in session.execute(stmt):
        available = product.is_active and item.qty <= product.stock_qty
        line_total = product.price_egp * item.qty
        if available:
            subtotal += line_total
        items.append(
            CartItemOut(
                product_id=product.id,
                title_ar=product.title_ar,
                qty=item.qty,
                unit_price_egp=product.price_egp,
                line_total_egp=line_total,
                stock_qty=product.stock_qty,
                available=available,
            )
        )
    return CartOut(items=items, subtotal_egp=subtotal)


def add_item(session: Session, user_id: int, product_id: int, qty: int) -> CartOut:
    product = _active_product(session, product_id)
    cart = _get_or_create_cart(session, user_id)
    item = _find_item(session, cart.id, product_id)
    new_qty = qty + (item.qty if item else 0)
    _check_stock(product, new_qty)
    if item is None:
        session.add(CartItem(cart_id=cart.id, product_id=product_id, qty=new_qty))
    else:
        item.qty = new_qty
    session.commit()
    return view_cart(session, user_id)


def set_qty(session: Session, user_id: int, product_id: int, qty: int) -> CartOut:
    product = _active_product(session, product_id)
    cart = _get_or_create_cart(session, user_id)
    item = _find_item(session, cart.id, product_id)
    if item is None:
        raise NotFoundError("Item is not in the cart", code="cart_item_not_found")
    _check_stock(product, qty)
    item.qty = qty
    session.commit()
    return view_cart(session, user_id)


def remove_item(session: Session, user_id: int, product_id: int) -> CartOut:
    cart = _get_or_create_cart(session, user_id)
    item = _find_item(session, cart.id, product_id)
    if item is None:
        raise NotFoundError("Item is not in the cart", code="cart_item_not_found")
    session.delete(item)
    session.commit()
    return view_cart(session, user_id)


def clear_cart(session: Session, user_id: int) -> CartOut:
    cart = session.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is not None:
        session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        session.commit()
    return view_cart(session, user_id)
