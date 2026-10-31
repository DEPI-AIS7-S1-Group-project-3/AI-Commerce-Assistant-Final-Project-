from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "customer"
    SELLER = "seller"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURN_REQUESTED = "return_requested"
    RETURNED = "returned"


class PaymentMethod(StrEnum):
    COD = "cod"
    WALLET = "wallet"
    CARD = "card"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class ActorType(StrEnum):
    CUSTOMER = "customer"
    SELLER = "seller"
    SYSTEM = "system"
    AGENT = "agent"


class ReturnStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECEIVED = "received"
    REFUNDED = "refunded"


class ReturnReason(StrEnum):
    DEFECTIVE = "defective"
    NOT_AS_DESCRIBED = "not_as_described"
    CHANGED_MIND = "changed_mind"
    WRONG_ITEM = "wrong_item"
    DAMAGED_IN_SHIPPING = "damaged_in_shipping"
    OTHER = "other"


class CancelReason(StrEnum):
    CUSTOMER_REQUEST = "customer_request"
    LATE_DELIVERY = "late_delivery"
    SELLER_OUT_OF_STOCK = "seller_out_of_stock"
    PAYMENT_FAILED = "payment_failed"
    OTHER = "other"


class SpecKind(StrEnum):
    MOBILE = "mobile"
    LAPTOP = "laptop"
    AUDIO = "audio"


class PolicyCategory(StrEnum):
    SHIPPING = "shipping"
    RETURNS = "returns"
    WARRANTY = "warranty"
    CANCELLATION = "cancellation"


def enum_check(column: str, enum_cls: type[StrEnum]) -> str:
    values = ", ".join(f"'{e.value}'" for e in enum_cls)
    return f"{column} IN ({values})"
