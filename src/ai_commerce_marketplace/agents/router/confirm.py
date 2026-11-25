"""The closed list of words that count as "yes".

Only the router uses this, and only when a ``pending_action`` is stored for the conversation.
The model never decides that the user said yes. Anything not on the list (including a longer
sentence that merely contains "yes") is not a confirmation, so a pending action is dropped and
the message is handled normally.
"""

from ai_commerce_marketplace.nlp.arabic import normalize_ar

_YES = {
    "ايوه",
    "ايوا",
    "أيوه",
    "اه",
    "اها",
    "اكيد",
    "تمام",
    "ماشي",
    "موافق",
    "نعم",
    "اي",
    "yes",
    "y",
    "ok",
    "okay",
    "sure",
    "confirm",
    "تمام الغي",
    "تمام الغيه",
    "ايوه الغي",
    "ايوه الغيه",
    "اكيد الغي",
    "اكيد الغيه",
    "ايوه ارجع",
    "اكيد ارجع",
    "تمام ارجع",
    "ايوه كمل",
    "كمل",
    "اكد",
    "اكده",
    "اكد الغاء",
    "اكد الالغاء",
    "اكد الارجاع",
}
_YES = {normalize_ar(w) for w in _YES}


def is_yes(message: str) -> bool:
    return normalize_ar(message) in _YES
