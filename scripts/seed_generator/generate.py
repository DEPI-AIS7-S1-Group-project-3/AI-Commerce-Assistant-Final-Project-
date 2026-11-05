"""Deterministic seed generator.

    python generate.py --out ../data/raw [--anchor-date 2026-10-31] [--seed 42]

All timestamps are relative to the anchor date (default: today 12:00 UTC), so "late" orders stay late.
"""

import argparse
import json
import math
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import catalog as C
import texts as T

NS = uuid.UUID("6f1d6f0e-3b5a-4c43-9b53-0a1e6c9a7e11")


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def money(x):
    return round(float(x), 2)


class Gen:
    def __init__(self, anchor, seed):
        self.now = anchor
        self.rng = random.Random(seed)
        self.products = C.build_products()
        self.pq = C.quality_for(self.products)
        self.by_id = {p["id"]: p for p in self.products}
        self.by_sku = {p["sku"]: p for p in self.products}

    def ago(self, days):
        return self.now - timedelta(days=days)

    # ───────── customers come from the team's base data (data/raw/users.json + addresses.json) ─────────
    def customers(self, base):
        users = [
            u
            for u in json.loads((base / "users.json").read_text(encoding="utf-8"))
            if u["role"] == "customer"
        ]
        addrs = json.loads((base / "addresses.json").read_text(encoding="utf-8"))
        cust = []
        for u in users:
            mine = [a for a in addrs if a["user_email"] == u["email"]]
            mine.sort(key=lambda a: not a["is_default"])  # default address first
            cust.append(dict(email=u["email"], name=u["full_name"], phone=u["phone"], addrs=mine))
        return cust

    # ───────── products ─────────
    def product_rows(self):
        rows, svg = [], []
        for p in self.products:
            created = self.ago(self.rng.randint(100, 170))
            n_img = 3 if p["price_egp"] > 20000 else (2 if p["price_egp"] > 3000 else 1)
            imgs = [
                dict(
                    url=f"/static/products/{p['sku']}-{k}.svg",
                    alt_ar=f"{p['title_ar']} - صورة {k}",
                    sort_order=k - 1,
                )
                for k in range(1, n_img + 1)
            ]
            brand = next(b for b in C.BRANDS if b[0] == p["brand_slug"])
            rows.append(
                dict(
                    sku=p["sku"],
                    seller_email=C.seller_email(p["seller_id"]),
                    category_slug=p["category_slug"],
                    brand_slug=p["brand_slug"],
                    title_ar=p["title_ar"],
                    description_ar=p["description_ar"],
                    price_egp=money(p["price_egp"]),
                    old_price_egp=money(p["old_price_egp"]) if p["old_price_egp"] else None,
                    stock_qty=p["stock_qty"],
                    warranty_months=p["warranty_months"],
                    is_returnable=p["is_returnable"],
                    is_active=p["is_active"],
                    specs=p["specs"],
                    created_at=iso(created),
                    images=imgs,
                )
            )
            for im in imgs:
                svg.append((im["url"].rsplit("/", 1)[1], p, im["sort_order"] + 1, brand[1]))
        return rows, svg

    # ───────── product / seller weights ─────────
    def weight(self, p, age):
        w = 1.0 / (p["price_egp"] ** 0.35)
        q = self.pq[p["id"]]
        if q["theme"] or q["mean"] >= 4.5:
            w *= 1.15
        recent = age < 30
        f = {1: (1.7, 0.7), 2: (1.4, 0.8), 3: (0.5, 1.5), 4: (1.0, 1.0)}[p["seller_id"]]
        return w * (f[0] if recent else f[1])

    def pick_product(self, age, ctx, seller=None, exclude=()):
        pool = []
        for p in self.products:
            if p["id"] in exclude or (seller and p["seller_id"] != seller):
                continue
            if ctx in ("returnable",):
                if not (p["is_returnable"] and p["is_active"]):
                    continue
            elif ctx == "live":
                if not (p["is_active"] and p["stock_qty"] > 0):
                    continue
            elif ctx == "active":
                if not p["is_active"]:
                    continue
            elif ctx == "old":
                if not p["is_active"] and age < 40:
                    continue
            pool.append(p)
        ws = [self.weight(p, age) * (0.4 if not p["is_active"] else 1) for p in pool]
        return self.rng.choices(pool, ws)[0]

    def qty_for(self, p):
        if p["kind"] == "audio" and p["specs"]["type"] in ("charger", "cable", "power_bank"):
            return self.rng.choices([1, 2, 3], [5, 3, 2])[0]
        return 2 if (p["kind"] == "mobile" and self.rng.random() < 0.08) else 1

    def unit_price(self, p, age, fixed=False):
        price = p["price_egp"]
        if not fixed and age > 45 and self.rng.random() < 0.5:
            price = price * self.rng.uniform(1.03, 1.10)
            step = 10 if price >= 1000 else 5
            price = max(step, round(price / step) * step)
            if p["old_price_egp"] and price >= p["old_price_egp"]:
                price = p["price_egp"]
        return money(price)

    # ───────── order assembly ─────────
    def make_items(self, products, age, fixed=False, single=False):
        items = []
        for p in products:
            qty = 1 if single else self.qty_for(p)
            items.append(dict(product=p, qty=qty, unit=self.unit_price(p, age, fixed)))
        return items

    def build_order(self, customer, addr, group, created, status, method, items, seller_id, **kw):
        sub = sum(i["qty"] * i["unit"] for i in items)
        fee = 0.0 if sub >= 5000 else 60.0
        fast = addr["governorate"] in C.FAST_GOVERNORATES
        exp = created + timedelta(days=2 if fast else 4)
        o = dict(
            group=group,
            customer=customer,
            seller_id=seller_id,
            status=status,
            method=method,
            addr=addr,
            items=items,
            subtotal=money(sub),
            fee=fee,
            created=created,
            expected=exp,
            delivered=None,
            cancelled=None,
            cancel_reason=None,
            hist=[],
            ret=None,
            demo=None,
        )
        o.update(kw)
        return o

    def timeline(self, o, spec):
        """spec: dict(kind=..., ...) -> fills created/hist/delivered/cancelled/ret. Times as datetimes."""
        r = self.rng
        c = o["created"]
        cu, su = o["customer"]["email"], C.seller_email(o["seller_id"])

        def h(frm, to, actor, when, reason=None, note=None):
            who = cu if actor == "customer" else (su if actor == "seller" else None)
            o["hist"].append(
                dict(
                    from_status=frm,
                    to_status=to,
                    actor_type=actor,
                    actor_email=who,
                    reason_code=reason,
                    note=note,
                    created=when,
                )
            )

        h(None, "pending", "system", c)
        kind = spec["kind"]
        age = (self.now - c).total_seconds() / 86400
        if kind == "pending":
            return
        t_conf = c + timedelta(hours=r.uniform(0.5, 6)) if age > 0.4 else c + (self.now - c) * 0.5
        t_conf = min(t_conf, self.now - timedelta(minutes=5))
        if kind == "confirmed":
            h("pending", "confirmed", "seller", t_conf)
            return
        if kind == "cancelled":
            reason = spec["reason"]
            actor = {
                "customer_request": "customer",
                "seller_out_of_stock": "seller",
                "payment_failed": "system",
                "other": "customer",
            }[reason]
            t_canc = c + timedelta(hours=r.uniform(1, 30))
            if r.random() < 0.4 and reason != "payment_failed":
                h("pending", "confirmed", "seller", c + (t_canc - c) * 0.4)
                h("confirmed", "cancelled", actor, t_canc, reason)
            else:
                h("pending", "cancelled", actor, t_canc, reason)
            o["cancelled"], o["cancel_reason"] = t_canc, reason
            return
        if kind in ("delivered", "returned", "return_requested", "rejected"):
            # الخطوات موزّعة بنسب ثابتة من مدة الطلب عشان الترتيب الزمني يفضل صحيح دايمًا
            span = (spec["delivered"] - c).total_seconds()
            t_conf = c + timedelta(seconds=span * r.uniform(0.03, 0.15))
            t_ship = c + timedelta(seconds=span * r.uniform(0.25, 0.55))
            t_ofd = c + timedelta(seconds=span * r.uniform(0.7, 0.92))
        else:
            t_ship = t_conf + timedelta(hours=r.uniform(6, 26))
            t_ofd = min(t_ship + timedelta(days=r.uniform(0.8, 2.0)), self.now - timedelta(hours=1))
        h("pending", "confirmed", "seller", t_conf)
        if kind == "shipped":
            t_ship = min(t_ship, self.now - timedelta(hours=2))
            h("confirmed", "shipped", "seller", t_ship)
            return
        h("confirmed", "shipped", "seller", t_ship)
        if kind == "ofd" and spec.get("ofd"):
            t_ofd = spec["ofd"]
        elif kind == "delivered" and spec.get("ofd") and spec.get("demo_ofd"):
            t_ofd = spec["ofd"]
        h("shipped", "out_for_delivery", "seller", t_ofd)
        if kind == "ofd":
            return
        t_del = spec["delivered"]
        h("out_for_delivery", "delivered", "seller", t_del)
        o["delivered"] = t_del
        if kind == "delivered":
            return
        rt = spec["ret_created"]
        h("delivered", "return_requested", "customer", rt, spec["ret_reason"])
        if kind == "return_requested":
            return
        if kind == "returned":
            h("return_requested", "returned", "seller", spec["ret_done"])
        elif kind == "rejected":
            h("return_requested", "delivered", "seller", spec["ret_done"], None, spec["ret_note"])

    # ───────── main order planning ─────────
    def plan_orders(self, cust):
        r = self.rng
        orders = []

        def pick_customer():
            return r.choice(cust)

        def pick_addr(c):
            a = c["addrs"]
            return a[0] if (len(a) == 1 or r.random() < 0.7) else r.choice(a[1:])

        def method():
            return r.choices(["cod", "card", "wallet"], [60, 25, 15])[0]

        def grp(tag):
            return str(uuid.uuid5(NS, tag))

        # ── 5 demo orders (ids 10001..10005, each a different customer)
        def demo(num, cidx, sku, age_created, method_, spec, qty=1, **kw):
            c = cust[cidx]
            p = self.by_sku[sku]
            created = self.ago(age_created)
            o = self.build_order(
                c,
                c["addrs"][0],
                grp(f"demo{num}"),
                created,
                spec["status"],
                method_,
                [dict(product=p, qty=qty, unit=money(p["price_egp"]))],
                p["seller_id"],
            )
            self.timeline(o, spec)
            o["demo"] = num
            orders.append(o)
            return o

        # 10001: late out_for_delivery, card, Assiut (+4 days) created 9 days ago -> expected 5 days ago
        demo(
            10001,
            2,
            "LAP-LEN-L5-16-512",
            9,
            "card",
            dict(kind="ofd", status="out_for_delivery", ofd=self.ago(7)),
        )
        demo(10002, 0, "AUD-JBL-H4", 1.0, "cod", dict(kind="confirmed", status="confirmed"))
        demo(
            10003,
            1,
            "MOB-SAM-D350-8-256",
            6,
            "wallet",
            dict(kind="delivered", status="delivered", delivered=self.ago(3), ofd=self.ago(4)),
        )
        demo(
            10004,
            4,
            "MOB-XIA-D14Plus-8-256",
            35,
            "cod",
            dict(kind="delivered", status="delivered", delivered=self.ago(31), ofd=self.ago(32)),
        )
        demo(
            10005,
            3,
            "AUD-BAS-H9",
            12,
            "card",
            dict(kind="cancelled", status="cancelled", reason="customer_request"),
        )
        # demo 10001: the courier created expected=created+4 for Assiut; make sure it is exactly 5 days ago
        # (created = now-9d, +4d -> now-5d)

        # ── regular orders
        plan = []  # (status-kind, count_single, count_pair)
        plan += [
            ("delivered", 52, 8),
            ("returned", 8, 0),
            ("return_requested", 6, 0),
            ("cancelled", 9, 1),
            ("shipped", 5, 1),
            ("ofd", 4, 0),
            ("confirmed", 3, 1),
            ("pending", 4, 1),
        ]
        status_name = {"ofd": "out_for_delivery"}
        rejected_left = 3
        n_checkout = 0
        for kind, n_single, n_pair in plan:
            units = [("single",)] * n_single + [("pair",)] * n_pair
            for u in units:
                n_checkout += 1
                c = pick_customer()
                addr = pick_addr(c)
                m = method()
                spec_kind = kind
                # age by kind
                if kind == "delivered":
                    age = r.uniform(6, 90)
                    if rejected_left and u[0] == "single" and r.random() < 0.15:
                        rejected_left -= 1
                        spec_kind = "rejected"
                        age = r.uniform(14, 55)
                elif kind == "returned":
                    age = r.uniform(25, 78)
                elif kind == "return_requested":
                    age = r.uniform(8, 16)
                elif kind == "cancelled":
                    age = r.uniform(3, 88)
                elif kind == "shipped":
                    age = r.uniform(2.2, 6)
                elif kind == "ofd":
                    age = r.uniform(3.3, 6)
                elif kind == "confirmed":
                    age = r.uniform(0.3, 2.0)
                else:
                    age = r.uniform(0.02, 0.6)
                created = self.ago(age)
                g = grp(f"co{n_checkout}")
                ctx = {
                    "returned": "returnable",
                    "return_requested": "returnable",
                    "rejected": "returnable",
                    "delivered": "old",
                    "cancelled": "active",
                }.get(spec_kind, "live")
                ctx = (
                    "returnable"
                    if spec_kind in ("returned", "return_requested", "rejected")
                    else ctx
                )
                single = spec_kind in ("returned", "return_requested", "rejected")
                if u[0] == "pair":
                    p1 = self.pick_product(age, ctx)
                    p2 = self.pick_product(age, ctx, exclude=(p1["id"],))
                    tries = 0
                    while p2["seller_id"] == p1["seller_id"] and tries < 50:
                        p2 = self.pick_product(age, ctx, exclude=(p1["id"],))
                        tries += 1
                    groups = [[p1], [p2]]
                else:
                    p1 = self.pick_product(age, ctx)
                    prods = [p1]
                    if not single and r.random() < 0.4:
                        try:
                            prods.append(
                                self.pick_product(
                                    age, ctx, seller=p1["seller_id"], exclude=(p1["id"],)
                                )
                            )
                        except IndexError:
                            pass
                    groups = [prods]
                for prods in groups:
                    items = self.make_items(prods, age, single=single)
                    o = self.build_order(
                        c,
                        addr,
                        g,
                        created,
                        status_name.get(kind, kind) if spec_kind != "rejected" else "delivered",
                        m,
                        items,
                        prods[0]["seller_id"],
                    )
                    sp = dict(kind=spec_kind)
                    exp_days = 2 if addr["governorate"] in C.FAST_GOVERNORATES else 4
                    if spec_kind in ("delivered", "returned", "return_requested", "rejected"):
                        dur = max(
                            1.0,
                            exp_days
                            + r.choice([-1, -0.5, 0, 0, 0.5, 0.5, 0.5, 1.5, 3])
                            + r.uniform(0, 0.4),
                        )
                        sp["delivered"] = created + timedelta(days=dur)
                        if sp["delivered"] > self.now - timedelta(hours=2):
                            sp["delivered"] = self.now - timedelta(days=r.uniform(2.0, 3.5))
                            if sp["delivered"] <= created + timedelta(days=1):
                                sp["delivered"] = created + timedelta(days=1.2)
                        sp["ofd"] = sp["delivered"] - timedelta(hours=r.uniform(3, 20))
                    if spec_kind == "return_requested":
                        room = min(10, (self.now - sp["delivered"]).total_seconds() / 86400 - 0.05)
                        sp["ret_created"] = sp["delivered"] + timedelta(
                            days=r.uniform(0.2, max(0.25, room))
                        )
                        sp["ret_reason"] = r.choice(
                            [
                                "defective",
                                "not_as_described",
                                "changed_mind",
                                "wrong_item",
                                "damaged_in_shipping",
                            ]
                        )
                    elif spec_kind == "returned":
                        sp["ret_created"] = sp["delivered"] + timedelta(days=r.uniform(1, 6))
                        sp["ret_done"] = sp["ret_created"] + timedelta(days=r.uniform(2, 6))
                        sp["ret_reason"] = r.choice(
                            [
                                "defective",
                                "not_as_described",
                                "wrong_item",
                                "damaged_in_shipping",
                                "changed_mind",
                            ]
                        )
                    elif spec_kind == "rejected":
                        sp["ret_created"] = sp["delivered"] + timedelta(days=r.uniform(1, 5))
                        sp["ret_done"] = sp["ret_created"] + timedelta(days=r.uniform(1, 3))
                        sp["ret_reason"] = r.choice(["changed_mind", "other"])
                        sp["ret_note"] = r.choice(T.REJECT_NOTE)
                    if spec_kind == "cancelled":
                        reasons = [
                            "customer_request",
                            "customer_request",
                            "customer_request",
                            "seller_out_of_stock",
                            "other",
                        ]
                        if m != "cod":
                            reasons.append("payment_failed")
                        sp["reason"] = r.choice(reasons)
                    o["spec"] = sp
                    self.timeline(o, sp)
                    orders.append(o)
        # payment status
        for o in orders:
            st, m = o["status"], o["method"]
            if m == "cod":
                o["pay"] = (
                    "paid"
                    if (o["delivered"] and st in ("delivered", "return_requested", "returned"))
                    else "pending"
                )
                if st == "returned":
                    o["pay"] = (
                        "refunded"
                        if o.get("spec", {}).get("ret_done") and r.random() < 0.75
                        else "paid"
                    )
            else:
                o["pay"] = "pending" if st == "pending" else "paid"
                if st == "cancelled":
                    o["pay"] = "failed" if o["cancel_reason"] == "payment_failed" else "refunded"
                if st == "returned":
                    o["pay"] = "refunded" if r.random() < 0.75 else "paid"
            # COD that was delivered then returned & refunded stays 'refunded'; cod cancelled -> pending
            # card/wallet pending orders: payment not captured yet
            if o["demo"] == 10001:
                o["pay"] = "paid"
        return orders

    # ───────── finalize ids, rows ─────────
    def finalize(self, orders, cust):
        r = self.rng
        demo = sorted([o for o in orders if o["demo"]], key=lambda o: o["demo"])
        reg = sorted(
            [o for o in orders if not o["demo"]], key=lambda o: (o["created"], o["seller_id"])
        )
        for n, o in enumerate(demo):
            o["id"] = o["demo"]
        for n, o in enumerate(reg):
            o["id"] = 10006 + n
        allo = demo + reg
        rows, returns, reviews = [], [], []
        for o in allo:
            row_items = []
            for it in o["items"]:
                p = it["product"]
                row_items.append(
                    dict(
                        product_sku=p["sku"],
                        product_title_snapshot=p["title_ar"],
                        qty=it["qty"],
                        unit_price_egp=it["unit"],
                    )
                )
            hist = []
            for hh in sorted(o["hist"], key=lambda x: x["created"]):
                hist.append(
                    dict(
                        from_status=hh["from_status"],
                        to_status=hh["to_status"],
                        actor_type=hh["actor_type"],
                        actor_email=hh["actor_email"],
                        reason_code=hh["reason_code"],
                        note=hh["note"],
                        created_at=iso(hh["created"]),
                    )
                )
            a = o["addr"]
            rows.append(
                dict(
                    id=o["id"],
                    checkout_group_id=o["group"],
                    customer_email=o["customer"]["email"],
                    seller_email=C.seller_email(o["seller_id"]),
                    status=o["status"],
                    payment_method=o["method"],
                    payment_status=o["pay"],
                    shipping_address=dict(
                        recipient_name=a["recipient_name"],
                        phone=a["phone"],
                        governorate=a["governorate"],
                        city=a["city"],
                        street_address=a["street_address"],
                    ),
                    subtotal_egp=o["subtotal"],
                    shipping_fee_egp=o["fee"],
                    total_egp=money(o["subtotal"] + o["fee"]),
                    expected_delivery_at=iso(o["expected"]),
                    delivered_at=iso(o["delivered"]) if o["delivered"] else None,
                    cancelled_at=iso(o["cancelled"]) if o["cancelled"] else None,
                    cancel_reason_code=o["cancel_reason"],
                    created_at=iso(o["created"]),
                    updated_at=hist[-1]["created_at"],
                    items=row_items,
                    status_history=hist,
                )
            )
            sp = o.get("spec", {})
            if sp.get("kind") in ("return_requested", "returned", "rejected"):
                it = o["items"][0]
                reason = sp["ret_reason"]
                if sp["kind"] == "return_requested":
                    st, upd = "requested", sp["ret_created"]
                elif sp["kind"] == "rejected":
                    st, upd = "rejected", sp["ret_done"]
                else:
                    st = "refunded" if o["pay"] == "refunded" else "received"
                    upd = sp["ret_done"]
                returns.append(
                    dict(
                        order_id=o["id"],
                        product_sku=it["product"]["sku"],
                        requested_by_email=o["customer"]["email"],
                        qty=it["qty"],
                        reason_code=reason,
                        reason_text=r.choice(T.RETURN_TEXT[reason]),
                        status=st,
                        created_at=iso(sp["ret_created"]),
                        updated_at=iso(upd),
                    )
                )
        # reviews
        for o in allo:
            if o["status"] not in ("delivered", "returned") or not o["delivered"]:
                continue
            for it in o["items"]:
                p = it["product"]
                since = (self.now - o["delivered"]).total_seconds() / 86400
                if since <= 3.5:
                    continue
                returned = o["status"] == "returned"
                if r.random() > (0.7 if returned else 0.97):
                    continue
                if o["id"] == 10004:
                    pass
                q = self.pq[p["id"]]
                if returned:
                    rating = r.choices([1, 2, 3], [4, 4, 2])[0]
                else:
                    mu = q["mean"]
                    ws = [math.exp(-((k - mu) ** 2) / (2 * 0.75**2)) for k in range(1, 6)]
                    rating = r.choices([1, 2, 3, 4, 5], ws)[0]
                late = (o["delivered"] - o["expected"]).total_seconds() / 86400 > 1.0
                parts = []
                if returned:
                    parts.append(r.choice(T.RETURNED_NEG))
                else:
                    if rating >= 4:
                        parts.append(r.choice(T.POS_GENERIC))
                        if r.random() < 0.7:
                            parts.append(r.choice(self.kind_lines(p)))
                        if q["theme"] and rating == 4 and r.random() < 0.5:
                            parts = [r.choice(T.MIX), r.choice(T.THEME[q["theme"]])]
                    elif rating == 3:
                        parts.append(r.choice(T.MIX))
                        if q["theme"] and r.random() < 0.8:
                            parts.append(r.choice(T.THEME[q["theme"]]))
                    else:
                        parts.append(r.choice(T.NEG))
                        if q["theme"] and r.random() < 0.85:
                            parts.append(r.choice(T.THEME[q["theme"]]))
                    if late and r.random() < 0.45:
                        parts.append(r.choice(T.LATE))
                        rating = min(rating, 3)
                    elif r.random() < 0.04:
                        parts.append(r.choice(T.PACK))
                        rating = min(rating, 3)
                when = min(
                    o["delivered"] + timedelta(days=r.uniform(0.3, 9)),
                    self.now - timedelta(hours=3),
                )
                reviews.append(
                    dict(
                        order_id=o["id"],
                        product_sku=p["sku"],
                        customer_email=o["customer"]["email"],
                        rating=rating,
                        body=" ".join(parts),
                        is_verified_purchase=True,
                        created_at=iso(when),
                    )
                )
        reviews.sort(key=lambda x: x["created_at"])
        return rows, returns, reviews

    def kind_lines(self, p):
        if p["kind"] != "audio":
            return T.POS_KIND[p["kind"]]
        typ = p["specs"]["type"]
        if typ in ("charger", "power_bank", "cable"):
            return T.POS_KIND["charge"]
        pool = list(T.POS_KIND["sound"])
        if typ in ("earbuds", "headphones"):
            pool += T.POS_KIND["wear"]
        return pool

    def carts(self, cust):
        r = self.rng
        out = []
        shop = [p for p in self.products if p["is_active"] and p["stock_qty"] > 2]
        for n, c in enumerate(cust):
            items = []
            if n in (0, 5, 7, 10):
                for p in r.sample(shop, r.randint(1, 3)):
                    items.append(
                        dict(
                            product_sku=p["sku"],
                            qty=r.choice([1, 1, 2]),
                            added_at=iso(self.ago(r.uniform(0.1, 6))),
                        )
                    )
            out.append(
                dict(
                    customer_email=c["email"],
                    updated_at=iso(self.ago(r.uniform(0.1, 6))),
                    items=items,
                )
            )
        return out


def svg_for(p, n, brand):
    col = {
        "mobile": ("#E6F0FF", "#1D4ED8"),
        "laptop": ("#E8F7EF", "#047857"),
        "audio": ("#FFF1E6", "#C2410C"),
    }[p["kind"]]
    shape = {
        "mobile": f'<rect x="{150 + 10 * (n - 1)}" y="70" width="100" height="180" rx="16" fill="none" stroke="{col[1]}" stroke-width="6"/><circle cx="{200 + 10 * (n - 1)}" cy="232" r="6" fill="{col[1]}"/>',
        "laptop": f'<rect x="110" y="90" width="180" height="110" rx="8" fill="none" stroke="{col[1]}" stroke-width="6"/><path d="M90 215h220l-16 18H106z" fill="{col[1]}"/>',
        "audio": f'<path d="M120 190v-30a80 80 0 0 1 160 0v30" fill="none" stroke="{col[1]}" stroke-width="8"/><rect x="104" y="180" width="32" height="56" rx="12" fill="{col[1]}"/><rect x="264" y="180" width="32" height="56" rx="12" fill="{col[1]}"/>',
    }[p["kind"]]
    model = p["sku"].split("-", 2)[2] if p["sku"].count("-") >= 2 else p["sku"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300">'
        f'<rect width="400" height="300" fill="{col[0]}"/>{shape}'
        f'<text x="200" y="272" font-family="sans-serif" font-size="16" text-anchor="middle" fill="{col[1]}">'
        f"{brand} {model} · {n}</text></svg>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base", required=True, help="the repo's data/raw (users.json, addresses.json ...)"
    )
    ap.add_argument("--out", required=True)
    ap.add_argument("--static", required=True, help="static/products output dir")
    ap.add_argument("--anchor-date", default="2026-11-04")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    anchor = datetime.fromisoformat(a.anchor_date).replace(hour=12, tzinfo=UTC)
    g = Gen(anchor, a.seed)
    out = Path(a.out)
    st = Path(a.static)
    out.mkdir(parents=True, exist_ok=True)
    st.mkdir(parents=True, exist_ok=True)

    cust = g.customers(Path(a.base))
    prod_rows, svgs = g.product_rows()
    orders = g.plan_orders(cust)
    order_rows, returns, reviews = g.finalize(orders, cust)
    carts = g.carts(cust)

    def dump(name, obj):
        (out / name).write_text(
            json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )

    dump("products.json", prod_rows)
    dump("orders.json", order_rows)
    dump("returns.json", returns)
    dump("reviews.json", reviews)
    dump("carts.json", carts)
    dump(
        "policies.json",
        [
            dict(
                slug=p["slug"],
                category=p["category"],
                title_ar=p["title_ar"],
                body_md=p["body_md"],
                version=T.POLICY_VERSION,
                is_demo=True,
                is_current=True,
            )
            for p in T.POLICIES
        ],
    )
    for fn, p, n, br in svgs:
        (st / fn).write_text(svg_for(p, n, br), encoding="utf-8")
    meta = dict(
        anchor=iso(anchor),
        seed=a.seed,
        orders=len(order_rows),
        reviews=len(reviews),
        returns=len(returns),
        products=len(prod_rows),
    )
    dump("_meta.json", meta)
    print(meta)


if __name__ == "__main__":
    main()
