#!/usr/bin/env python3
"""Self-check of the CLEAN base of the affiliate landscape.

The clean base is the true world played through the ERP model, before any
disorder is applied. Every check here must pass on it, so that every
inconsistency in the delivered data is one the generator put there.

    .venv/bin/python corpora/affiliate/generator/selfcheck.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Orders of the true world on which an invoice is paid although no receipt is
# recorded (yet). These are facts of the true world, not errors of the data.
PAID_WITHOUT_RECEIPT_TAGS = {"R1", "R2", "R3", "R4", "K4a", "K4b", "T1", "T2", "T3", "T4", "T5", "T6", "L1"}


def run_checks(W, T):
    import generate_affiliate as g
    res = []

    def check(name, bad):
        bad = list(bad)
        res.append((name, not bad, bad[:5]))

    lines = {(po.key, l.pos): (po, l) for po in W.pos for l in po.lines}

    # 1 purchase orders
    check("order currency equals vendor currency", [po.key for po in W.pos if po.cur != W.vendors[po.vend].cur])
    check("promised date recorded exactly for orders from 1 July",
          [po.key for po in W.pos for l in po.lines if (l.promised_rec is None) != (po.date < g.CUT)])
    check("order lines have positive quantity and price",
          [po.key for po in W.pos for l in po.lines if l.qty <= 0 or l.price0 <= 0])

    # 2 goods receipts
    grq, grv = defaultdict(F), defaultdict(int)
    bad_ref, bad_mat, bad_rev, bad_bu = [], [], [], []
    reversed_qty = defaultdict(F)
    for r in T.gr:
        k = (r.po.key, r.popos)
        if k not in lines:
            bad_ref.append(r.doc)
            continue
        po, l = lines[k]
        if r.mat != l.mat:
            bad_mat.append(r.doc)
        if F(r.qty_bu) != F(r.qty) * W.mats[r.mat].conv:
            bad_bu.append(r.doc)
        s = 1 if r.mvt == "101" else -1
        if s < 0:
            if r.it.rev is None or r.it.rev.pos != r.popos or not r.rev_ref:
                bad_rev.append(r.doc)
            else:
                reversed_qty[id(r.it.rev)] += F(r.qty)
                if reversed_qty[id(r.it.rev)] > F(r.it.rev.qty):
                    bad_rev.append(r.doc)
        grq[k] += s * F(r.qty)
        grv[k] += s * r.lc
    check("every receipt refers to an existing order line", bad_ref)
    check("receipt material equals order line material", bad_mat)
    check("receipt base quantity equals quantity times conversion", bad_bu)
    check("every reversal refers to a receipt of the same line and does not exceed it", bad_rev)
    check("net received quantity between zero and order quantity plus 8 %",
          [k for k, q in grq.items() if q < 0 or q > F(lines[k][1].qty) * F(108, 100)])
    check("receipts are posted on or after the delivery note date and within the data period",
          [r.doc for r in T.gr if r.post < r.docdt or r.post > g.YE])

    # 3 invoices
    irq, irv = defaultdict(F), defaultdict(int)
    bad = []
    for x in T.invl:
        l, e = x.l, x.e
        if l.po is None:
            if not l.gl:
                bad.append(x.doc)
            continue
        k = (l.po.key, l.pos)
        m = W.mats[l.mat]
        if k not in lines or l.po.vend != e.vend or e.cur != l.po.cur or l.uom not in (m.ou, m.bu) \
                or l.mat != lines[k][1].mat:
            bad.append(x.doc)
            continue
        s = 1 if e.typ == "RE" else -1
        q = F(l.qty, m.conv) if (l.uom == m.bu and m.bu != m.ou) else F(l.qty)
        irq[k] += s * q
        irv[k] += s * g.rnd(l.net * (g.book(e.post) if e.cur == "EUR" else 1))
    check("invoice lines refer to an order line of the same vendor, currency, material and a valid unit", bad)
    check("net invoiced quantity between zero and order quantity",
          [k for k, q in irq.items() if q < 0 or q > lines[k][1].qty])
    check("invoice header: tax is the rate times net, gross is net plus tax",
          [h.doc for h in T.invh if h.gross != h.net + h.tax or h.tax != g.rnd(h.net * h.e.taxrate)
           or h.net != sum(l.net for l in h.e.lines)])
    check("vendor reference unique per vendor",
          [h.doc for h in T.invh if sum(1 for o in T.invh if o.e.vend == h.e.vend and o.e.ref == h.e.ref) > 1])

    # 4 payments
    seen = defaultdict(int)
    bad = []
    for p in T.pay:
        seen[p.inv.seq] += 1
        s = 1 if p.inv.typ == "RE" else -1
        if p.amt != s * g.inv_total(p.inv)[2] or p.cur != p.inv.cur or p.date <= p.inv.post or p.date > g.YE:
            bad.append(p.doc)
    check("each payment settles one invoice in full, in its currency, after posting", bad)
    check("no invoice is paid twice", [k for k, n in seen.items() if n > 1])

    # 5 ledger
    tot = defaultdict(int)
    for r in T.gl_all:
        tot[r.doc] += r.amt
    check("every ledger document balances", [d for d, x in tot.items() if x])

    auto = defaultdict(int)
    full = defaultdict(int)
    for r in T.gl_all:
        if r.acct in g.GRIR:
            full[r.line] += r.amt
            if r.typ in ("WE", "RE", "KG"):
                auto[r.line] += r.amt
    bad = []
    target = {}
    for k in lines:
        gq, gv, iq, iv = grq[k], grv[k], irq[k], irv[k]
        if gq > iq and gq > 0:
            t = -g.rnd((gq - iq) * F(gv) / gq)
        elif iq > gq and iq > 0:
            t = g.rnd((iq - gq) * F(iv) / iq)
        else:
            t = 0
        target[k] = t
        if auto[k] != t:
            bad.append((k, auto[k], t))
    check("clearing account per order line equals receipts minus invoices from the subledger", bad)
    check("clearing account in total equals receipts minus invoices plus automatic differences",
          [1] if sum(auto.values()) != sum(target.values()) else [])
    check("no clearing posting without an order line", [1] if full.get(None, 0) or None in full else [])
    check("fully matched order lines carry no balance",
          [k for k in lines if grq[k] == irq[k] and auto[k] != 0])

    ext = defaultdict(int)
    for r in T.gl:
        if r.acct in g.GRIR:
            ext[r.line] += r.amt
    check("extract with opening items equals the full ledger on the clearing accounts",
          [k for k in set(ext) | set(full) if ext[k] != full[k]])

    # manual journals of the clean base: only correct clearings and the transit reclassification
    mj_lines = set()
    bad = []
    for e in W.ev:
        if e.k == "MJ":
            for it in e.items:
                k = (it.po.key, it.pos)
                mj_lines.add(k)
                if it.acct or it.factor != 1 or it.amt is not None or e.lump:
                    bad.append(e.no)
                if full[k] != 0 or target[k] >= 0:
                    bad.append(e.no)
    check("manual clearings bring a credit remainder to exactly zero, with order reference", bad)
    check("group order lines carry no debit balance after the year-end reclassification",
          [k for k in lines if W.vendors[lines[k][0].vend].cat == "IC" and full[k] > 0])
    check("credit balance per line equals value of quantity received and not invoiced, unless cleared",
          [k for k in lines if k not in mj_lines and min(full[k], 0) != min(target[k], 0)])

    ap = defaultdict(int)
    for r in T.gl_all:
        if r.acct in ("3300", "3310", "3350"):
            ap[r.doc] += r.amt
    check("vendor account per invoice equals gross amount in local currency",
          [h.doc for h in T.invh if -ap[h.doc] != (1 if h.e.typ == "RE" else -1) * h.e.lc])

    # 6 mapping
    bad = []
    used = {(r.acct, r.post) for r in T.gl if r.acct in g.EXTRACT_ACCTS}
    for acct, post in used:
        if sum(1 for m in W.mapping if m.loc == acct and m.vfrom <= post <= m.vto) != 1:
            bad.append((acct, post))
    check("every posted account has exactly one valid mapping row on the posting date", sorted(bad))

    # 7 numbering
    for name, nos, dates in (("order", [po.no for po in W.pos], [po.date for po in W.pos]),
                             ("receipt", [e.no for e in W.ev if e.k == "GR"], [e.post for e in W.ev if e.k == "GR"]),
                             ("invoice", [e.no for e in W.ev if e.k == "INV"],
                              [e.post for e in W.ev if e.k == "INV"])):
        check(f"{name} numbers are unique", [n for n in set(nos) if nos.count(n) > 1])
        check(f"{name} numbers follow the scheme of their date",
              [n for n, d in zip(nos, dates) if ("-" in n) != (d >= g.CUT)])

    # 8 paid-without-receipt only where the true world says so
    ye, atpay = g.q2_flags(T)
    allowed = {W.tags[t].po.key for t in PAID_WITHOUT_RECEIPT_TAGS}
    check("no payment without receipt outside the known true cases",
          [k for (_, k) in list(ye) + list(atpay) if k[0] not in allowed])

    check("twelve monthly rates", [m for m in range(1, 13) if (2025, m) not in g.EOM])
    return res


def main():
    import generate_affiliate as g
    W = g.build_true_world()
    T = g.simulate(W)
    res = run_checks(W, T)
    failed = [r for r in res if not r[1]]
    for name, ok, detail in res:
        if not ok:
            print(f"FAIL  {name}  {detail}")
    print(f"{len(res) - len(failed)} of {len(res)} checks passed on the clean base")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
