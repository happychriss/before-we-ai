"""Writes answer-key/ANSWER_KEY.md from the true world and the recorded world.

DO NOT READ if you are implementing or testing against this landscape.
"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction as F

import generate_affiliate as g


def m(c):
    return f"{c / 100:,.2f}"


def eur(c, rate=None):
    return f"{float(F(c) / (rate or g.CLOSING)) / 100:,.2f}"


def write(Wt, Tt, Wr, Tr, path):
    out = []
    w = out.append
    tag = lambda t: Wr.tags[t]
    pono = lambda t: tag(t).po.no
    key_tag = {p.key: p.tag for p in Wr.pos}
    po_by_key = {p.key: p for p in Wr.pos}
    vname = lambda no: Wr.vendors[no].name
    lref = lambda k: f"{po_by_key[k[0]].no}/{k[1]}"

    bt, br = g.line_balances(Tt), g.line_balances(Tr)
    true_lines = {k: -x for k, x in bt.items() if x < 0}
    true_grni = sum(true_lines.values())
    is_ic = lambda k: Wr.vendors[po_by_key[k[0]].vend].cat == "IC"
    true_ic = sum(x for k, x in true_lines.items() if is_ic(k))
    true_debit = sum(x for x in bt.values() if x > 0)
    rec_acct = defaultdict(int)
    for r in Tr.gl:
        if r.acct in g.GRIR:
            rec_acct[r.acct] += r.amt
    rec_net = sum(rec_acct.values())
    rec_credit = sum(-x for k, x in br.items() if k is not None and x < 0)
    rec_debit = sum(x for k, x in br.items() if k is not None and x > 0)
    rec_unassigned = br.get(None, 0)
    rec_credit_2815 = 0
    per = defaultdict(int)
    for r in Tr.gl:
        if r.acct in g.GRIR and r.line is not None:
            per[(r.line, r.acct)] += r.amt
    rec_2815_lines = defaultdict(int)
    for (k, a), x in per.items():
        if a == "2815":
            rec_2815_lines[k] += x
    qty_based = 0
    for k, st in Tr.S.items():
        if st.grq > st.irq:
            qty_based += g.rnd((st.grq - st.irq) * st.line.price0 * (g.CLOSING if st.po.cur == "EUR" else 1))

    delta = defaultdict(int)
    for k in set(bt) | set(br):
        if k is None:
            continue
        d = max(0, -br.get(k, 0)) - max(0, -bt.get(k, 0))
        if d:
            t = key_tag[k[0]]
            assert t, ("unexplained difference on an untagged order line", k, d)
            delta[t[:2] if t[:2] in ("B2", "D3") else t] += d
    k3 = -delta["K3"]
    assert rec_credit - sum(delta.values()) == true_grni

    w("# ANSWER KEY - affiliate landscape (Meridia Pharma Norvania d.o.o., FY2025)\n")
    w("**Do not read if you implement or test against this landscape.** Written by "
      "`generator/generate_affiliate.py` (seed 20251003); every number below is computed, not typed.\n")
    w("Conventions: amounts in NVK unless stated; EUR at the December month-end rate "
      f"{g.EOM[(2025, 12)]} NVK per EUR (group manual 7.4) unless stated. Order lines are written "
      "`po_no/pos`. \"True\" means what the generator knows happened; \"establishable\" means what a "
      "careful analyst can derive from `data/` alone.\n")

    # ------------------------------------------------------------------ Q1
    w("## Question 1 - goods received but not yet invoiced at year end, in EUR\n")
    w(f"**True answer: NVK {m(true_grni)} = EUR {eur(true_grni)}** "
      f"(third parties NVK {m(true_grni - true_ic)} = EUR {eur(true_grni - true_ic)}; group supply company "
      f"NVK {m(true_ic)} = EUR {eur(true_ic)}), on {len(true_lines)} order lines.\n")
    w("Definition used (group manual 7.3): the sum of order lines whose clearing balance is a credit - "
      "received, invoice still expected. Debit lines (invoiced or paid, not received) are not netted. "
      "Remainders that were legitimately cleared by manual journal (no invoice expected) are not part of it.\n")
    w(f"**Establishable from the delivered data: EUR {eur(true_grni)} if the December write-off K3-1 is "
      f"treated as not permitted (it breaks group manual 7.5: far above the limit, item under 180 days "
      f"but no vendor confirmation in the data), or EUR {eur(true_grni - k3)} if it is accepted. "
      f"A good answer gives the range EUR {eur(true_grni - k3)} to EUR {eur(true_grni)} and names the "
      f"write-off as the reason.** Tolerance for scoring: an answer within about 2 % of either end, "
      "with the corrections named, is right; the uncorrected figures below are wrong.\n")
    w("What the data shows before any correction:\n")
    w("| figure | NVK | EUR |")
    w("|---|---:|---:|")
    w(f"| net balance of account 2810 at 31.12. | {m(rec_acct['2810'])} | {eur(rec_acct['2810'])} |")
    w(f"| net balance of account 2815 at 31.12. | {m(rec_acct['2815'])} | {eur(rec_acct['2815'])} |")
    w(f"| net balance 2810 + 2815 (negative = credit) | {m(rec_net)} | {eur(rec_net)} |")
    w(f"| sum of order lines with credit balance (by assignment field, both accounts) | {m(rec_credit)} | {eur(rec_credit)} |")
    w(f"| sum of order lines with debit balance | {m(rec_debit)} | {eur(rec_debit)} |")
    w(f"| clearing postings without order reference (debit) | {m(rec_unassigned)} | {eur(rec_unassigned)} |")
    w(f"| quantity view: (received - invoiced quantity) x order price, recorded currency | {m(qty_based)} | {eur(qty_based)} |")
    w("")
    w("Reconciliation from the recorded sum of credit lines to the true figure:\n")
    w("| step | case | NVK | EUR |")
    w("|---|---|---:|---:|")
    w(f"| recorded credit lines | | {m(rec_credit)} | {eur(rec_credit)} |")
    label = {"A1": "A-1 duplicate invoice hides a later receipt", "B1": "B-1 receipt on wrong line",
             "B2": "B-2 receipt on wrong order", "B3": "B-3 receipt on wrong line (wrong price)",
             "C1": "C-1 EUR order recorded in NVK", "D2": "D-2 clearing posted to inventory",
             "D3": "D-3 clearing without order reference", "D4": "D-4 clearing with wrong sign",
             "D5": "D-5 clearing with transposed amount", "F1": "F-1 receipt posted twice",
             "F2": "F-2 receipt posted twice", "K3": "K3-1 December write-off (undecidable)"}
    for t in sorted(delta):
        w(f"| remove effect of | {label[t]} | {m(-delta[t])} | {eur(-delta[t])} |")
    w(f"| **true** | | **{m(true_grni)}** | **{eur(true_grni)}** |")
    w("")
    w("Reasoning a careful analyst needs: (1) read 2810 and 2815 together and per order line, because "
      "orders invoiced before and received after 1 July have their legs on different accounts, and the "
      "assignment field changed format on 1 July; (2) include the opening items (document type SV) and "
      "the receipts of December 2024; (3) take only credit lines; (4) honour correct manual clearings "
      "but test each one against the subledger; (5) test each open line against quantities: received, "
      "reversed, invoiced, credited, in order units; (6) translate at the December month-end rate. "
      "The EUR items are carried in NVK at the booking rate of the receipt month; that is the ledger "
      "value and is what is translated.\n")
    w("True open lines (credit balance in the true world):\n")
    w("| order line | vendor | NVK |")
    w("|---|---|---:|")
    for k, x in sorted(true_lines.items(), key=lambda t: -t[1]):
        w(f"| {lref(k)} | {vname(po_by_key[k[0]].vend)} | {m(x)} |")
    w("")

    # ------------------------------------------------------------------ Q2
    ye_r, at_r = g.q2_flags(Tr)
    ye_t, at_t = g.q2_flags(Tt)
    expected = {"A1", "A2", "B1", "B2b", "H1", "K4a", "K4b", "L1", "R1", "R2", "R3", "R4",
                "T1", "T2", "T3", "T4", "T5", "T6"}
    got = {key_tag[k[0]] for (_, k) in list(ye_r) + list(at_r)}
    assert got == expected, got ^ expected
    pay_of = {}
    for p in Tr.pay:
        pay_of[p.inv.seq] = p

    def inv_row(e, note, true_gross=None, true_cur="NVK"):
        p = pay_of.get(e.seq)
        net, tax, gross = g.inv_total(e)
        tg = true_gross if true_gross is not None else gross
        rate = g.book(p.date) if p else g.CLOSING
        pos = sorted({l.po.no for l in e.lines if l.po is not None})
        return (f"| {e.no} | {vname(e.vend)} | {e.ref} | {', '.join(pos)} | {m(gross)} {e.cur} | "
                f"{p.date.isoformat() if p else 'unpaid'} | {(m(p.amt) + ' ' + p.cur) if p else ''} | "
                f"{m(tg)} | {eur(tg, rate)} | {note} |"), tg, int(F(tg) / rate)

    head = ("| inv_doc | vendor | vend_ref | order | gross as recorded | paid on | paid as recorded | "
            "true gross NVK | EUR (booking rate of payment month) | note |\n|---|---|---|---|---:|---|---:|---:|---:|---|")
    w("## Question 2 - vendor invoices paid without a goods receipt\n")
    core = [("R1", "no receipt recorded; goods never arrived"),
            ("R2", "no receipt recorded; payment amount differs from invoice, see K3-3"),
            ("R3", "no receipt recorded; invoice header carries the wrong currency, see C-2"),
            ("R4", "no receipt recorded by year end"),
            ("T6", "advance payment vendor (terms ADV), delivery due January 2026 - permitted by manual 7.1")]
    rows, tot, tot_e = [], 0, 0
    for t, note in core:
        r, a, e_ = inv_row(tag(t).inv, note)
        rows.append(r)
        tot += a
        tot_e += e_
    dup_rows, dtot, dtot_e = [], 0, 0
    for t in ("A1", "A2"):
        r, a, e_ = inv_row(tag(t).dup, f"duplicate of {tag(t).inv.no}; goods were received and paid once already")
        dup_rows.append(r)
        dtot += a
        dtot_e += e_
    lab_rows, ltot, ltot_e = [], 0, 0
    for t, note in (("K4a", "laboratory order; whether the goods arrived is undecidable (K3-2)"),
                    ("K4b", "laboratory order; whether the goods arrived is undecidable (K3-2)")):
        r, a, e_ = inv_row(tag(t).inv, note)
        lab_rows.append(r)
        ltot += a
        ltot_e += e_
    adv_rows, atot, atot_e = [], 0, 0
    for t in ("T1", "T2", "T3", "T4", "T5"):
        r, a, e_ = inv_row(tag(t).inv, f"advance payment vendor; receipt {tag(t).gr.no} posted "
                                       f"{tag(t).gr.post.isoformat()}")
        adv_rows.append(r)
        atot += a
        atot_e += e_
    nonpo = [h for h in Tr.invh if all(l.po is None for l in h.e.lines)]
    nonpo_paid = [h for h in nonpo if h.e.seq in pay_of]
    nonpo_sum = sum(h.gross for h in nonpo_paid)
    w(f"**True answer (paid by 31.12.2025, no receipt recorded by 31.12.2025): "
      f"{len(rows) + len(dup_rows) + len(lab_rows)} invoices, NVK {m(tot + dtot + ltot)} gross "
      f"= EUR {m(tot_e + dtot_e + ltot_e)}.** In three groups:\n")
    w(f"(a) Ordered goods invoiced and paid, no receipt: {len(rows)} invoices, NVK {m(tot)} = EUR {m(tot_e)}.\n")
    w(head)
    out.extend(rows)
    w("")
    w(f"(b) Duplicate invoices paid a second time - the second payment has no receipt behind it: "
      f"{len(dup_rows)} invoices, NVK {m(dtot)} = EUR {m(dtot_e)}.\n")
    w(head)
    out.extend(dup_rows)
    w("")
    w(f"(c) Laboratory orders, paid, no receipt in the system: {len(lab_rows)} invoices, NVK {m(ltot)} = "
      f"EUR {m(ltot_e)}. They belong in the answer as stated (no recorded receipt). In the generator's "
      f"true world the goods of {tag('K4a').inv.no} did arrive and were never booked; those of "
      f"{tag('K4b').inv.no} did not arrive. The data cannot tell the two apart.\n")
    w(head)
    out.extend(lab_rows)
    w("")
    w(f"**Establishable from the delivered data: the same {len(rows) + len(dup_rows) + len(lab_rows)} "
      f"invoices.** For the amount: NVK {m(tot + dtot + ltot)} (EUR {m(tot_e + dtot_e + ltot_e)}) taking "
      "invoice amounts in the vendor's currency; one payment record differs from its invoice by a "
      "transposition (K3-3), which moves the paid total by NVK 90.00 - a good answer states "
      "both. An answer that lists (a) and (b) and flags (c) as 'no recorded receipt, physical receipt "
      "unknown' is right. Leaving T6 out with the argument that advance payment is permitted is "
      "acceptable if stated.\n")
    w(f"A second, weaker reading - paid before the receipt was posted, receipt followed: {len(adv_rows)} "
      f"further invoices of the two advance-payment vendors, NVK {m(atot)} = EUR {m(atot_e)}. Permitted by "
      "group manual 7.1 (terms ADV in the vendor master). Worth mentioning, not part of the answer.\n")
    w(head)
    out.extend(adv_rows)
    w("")
    w("Why it is smaller than it first looks - things a naive rule flags that are NOT in the answer:\n")
    w(f"- {len(nonpo)} invoices have no purchase order at all (rent, utilities, leasing, services); "
      f"{len(nonpo_paid)} of them are paid, NVK {m(nonpo_sum)} gross. They are outside the three-way match "
      "(manual 7.1, instruction section 1). 'No receipt' means nothing for them.")
    b1 = tag("B1")
    w(f"- {b1.inv.no} (order {b1.po.no}): line 20 looks uncovered because its receipt was booked to line 10 "
      f"(case B-1). The goods arrived.")
    w(f"- {tag('B2b').inv.no} (order {pono('B2b')}): no receipt on the order because it was booked to order "
      f"{pono('B2a')} (case B-2). The goods arrived.")
    w(f"- {tag('H1').inv.no} (order {pono('H1')}): invoiced quantity looks 500 times the receipt because the "
      "pieces were entered with the order unit (case H-1). Fully received.")
    l1 = tag("L1")
    w(f"- {l1.inv.no} (order {l1.po.no}): fully received on {l1.gr.post.isoformat()} and paid; 50 rolls were "
      f"returned on {l1.ret.post.isoformat()} (document {l1.ret.no}) after the payment; the credit note had "
      "not arrived by year end. Paid WITH receipt; a refund is outstanding (kind 1, NVK "
      f"{m(50 * 9600 * 120 // 100)} gross).")
    w(f"- {tag('A3').dup.no}: a duplicate invoice (case A-3) that was posted but not paid by year end.")
    w("- Group invoices are posted before the receipt all year (goods in transit) but are paid only "
      "after the receipt; at year end the invoices in transit are unpaid.")
    w("- Receipts that were reversed and posted again, invoices in pieces against receipts in order units, "
      "several invoices per order line, credit notes: all covered when quantities are netted in order units.")
    w("- Receipts of December 2024 belong to invoices paid in early 2025.\n")

    # ------------------------------------------------------------------ Q3
    a = g.q3_measure(Tr, "promised_rec", "docdt")
    b = g.q3_measure(Tr, "promised_rec", "post")
    c = g.q3_measure(Tt, "promised_rec", "docdt")
    d = g.q3_measure(Tt, "promised_true", "docdt")
    f = g.q3_measure(Tt, "promised_true", "docdt", h2_only=False)
    od = g.q3_overdue(Tt, "promised_rec")
    h1_orders = sum(1 for p in Wr.pos if p.date < g.CUT)
    h2_orders = len(Wr.pos) - h1_orders

    def row(name, x):
        return (f"| {name} | {m(x.tot)} | {m(x.late)} | {x.share * 100:.1f} % | {m(x.tot_e)} | {m(x.late_e)} |")

    w("## Question 3 - how much of the purchase volume was delivered late\n")
    w(f"**The question can only be answered for orders placed from 1 July 2025.** The delivery date field "
      f"of the order line is empty for all {h1_orders} orders created before that date (never recorded; "
      f"instruction section 3, handover note) and filled for the {h2_orders} orders created from 1 July. "
      "A right answer says so and gives the second half-year only. An answer that gives a full-year figure, "
      "or treats empty dates as on time, is wrong.\n")
    w("Measure (group manual 7.7): per order line, value of the quantity whose delivery note date "
      "(`doc_dt`) is after the delivery date in the order line; reversals netted against the receipt they "
      "reverse; value = receipt value in NVK, EUR at the booking rate of the receipt month.\n")
    w("| basis | received NVK | of which late NVK | late share | received EUR | late EUR |")
    w("|---|---:|---:|---:|---:|---:|")
    w(row("**true, orders from 1 July, against the date in the order line (last agreed)**", c))
    w(row("true, orders from 1 July, against the date first promised (not in the data)", d))
    w(row("true, whole year, against the date first promised (not in the data)", f))
    w(row("delivered data as recorded, delivery note date", a))
    w(row("delivered data as recorded, posting date (naive)", b))
    w("")
    w(f"**Establishable: late share of about {c.share * 100:.0f} % of the value received on orders placed "
      f"from 1 July (NVK {m(c.late)} of {m(c.tot)}; EUR {m(c.late_e)} of {m(c.tot_e)}), measured against the "
      f"last agreed date.** The recorded data gives {a.share * 100:.1f} % before the receipt errors B-2, B-3 "
      f"and F-1 are corrected; anything within two percentage points of {c.share * 100:.0f} % with the "
      f"half-year restriction stated is right. Using the posting "
      f"date instead of the delivery note date overstates lateness ({b.share * 100:.1f} %): the warehouse "
      "posts up to three working days later and re-posts corrected receipts later still.\n")
    w(f"Not decidable (K3-4): purchasing overwrites the date when a vendor announces a delay. Against the "
      f"date first promised the true late share for the second half-year is {d.share * 100:.1f} %. The "
      f"{len(Wr.k7)} lines concerned carry a change date (`chgd_on`), but so do lines whose price was "
      "changed, so they cannot be isolated with certainty. A good answer names this as a reason the figure "
      "is a lower bound.\n")
    w(f"Open at year end and past the date in the order line (not delivered at all, orders from 1 July): "
      f"NVK {m(od)} at order price. In addition the whole first half-year: true late share for the full "
      f"year {f.share * 100:.1f} % - not derivable.\n")
    w("Lines whose date was overwritten: " + ", ".join(
        f"{lref(k)} (first promised {Tr.S[k].line.promised_true.isoformat()}, in data "
        f"{Tr.S[k].line.promised_rec.isoformat()})" for k in Wr.k7) + "\n")

    # ------------------------------------------------------------ seeded cases
    w("## Seeded cases, kind 2 - real errors, no note anywhere\n")

    def case(cid, title, records, wrong, effect, detect):
        w(f"### {cid} - {title}\n")
        w(f"- **Records:** {records}")
        w(f"- **What is wrong:** {wrong}")
        w(f"- **Effect:** {effect}")
        w(f"- **Detection:** {detect}\n")

    def gross_of(e):
        return g.inv_total(e)[2]

    for cid, t, extra in (("A-1", "A1", "The duplicate consumes the quantity of the later receipt "
                           f"{tag('A1').gr2.no} (40 pieces, 11.12.), so by quantity the line looks over-invoiced "
                           f"by 20 instead of open by 40. Q1: true open amount NVK {m(-delta['A1'])} hidden."),
                          ("A-2", "A2", "Q1: no effect on credit lines; debit balance on the clearing account."),
                          ("A-3", "A3", "Not paid by year end: no effect on Q2. Debit balance on the clearing "
                           "account; vendor payable overstated.")):
        x = tag(t)
        p = pay_of.get(x.dup.seq)
        case(cid, "vendor invoice posted twice under a slightly different reference",
             f"`inv_header`/`inv_lines` {x.inv.no} (vend_ref `{x.inv.ref}`) and {x.dup.no} (vend_ref "
             f"`{x.dup.ref}`), vendor {x.inv.vend} {vname(x.inv.vend)}, order {x.po.no}; payment "
             f"{p.doc + ' on ' + p.date.isoformat() if p else 'none for the duplicate'}.",
             f"{x.dup.no} is the same invoice as {x.inv.no}: same vendor, invoice date, order lines, "
             "quantities and amount; the reference differs only in punctuation or a leading zero.",
             f"Gross NVK {m(gross_of(x.dup))} (EUR {eur(gross_of(x.dup))}) booked twice"
             f"{', and paid twice (Q2 group b)' if p else ''}. {extra}",
             "Same vendor + invoice date + gross amount, references equal after removing punctuation and leading zeros; "
             "invoiced quantity exceeds received quantity on the order line.")

    x = tag("B1")
    case("B-1", "receipt booked to the wrong line of the same order",
         f"`goods_receipts` {x.gr.no}: two rows on order {x.po.no} position 10, the second with the material of "
         f"position 20; invoice {x.inv.no}.",
         "The 18 boxes of position 20 were received on position 10. The system valued them at the price of "
         "position 10.",
         f"Q1: false open item NVK {m(delta['B1'])} on {x.po.no}/10. Q2: {x.inv.no} looks paid without receipt "
         "for position 20 - it is not. Debit balance on position 20.",
         "`mat_no` of the receipt row differs from the material of the order line it points to; position 10 "
         "over-received by exactly the quantity position 20 lacks.")
    x, y = tag("B2a"), tag("B2b")
    case("B-2", "receipt booked to another order of the same vendor",
         f"`goods_receipts` {y.gr.no} on order {x.po.no}/10; belongs to order {y.po.no}/10; invoice {y.inv.no}.",
         f"Order {x.po.no} (80 cartons) was complete since {x.gr.post.isoformat()}; the delivery of "
         f"{y.gr.doc.isoformat()} for order {y.po.no} (same material, 80 cartons, other price) was received "
         "against it.",
         f"Q1: false open item NVK {m(delta['B2'])} on {x.po.no}/10. Q2: {y.inv.no} looks paid without receipt - "
         f"it is not. Q3: the receipt counts as very late against the date of {x.po.no}; in truth on time.",
         f"{x.po.no}/10 received twice its order quantity, {y.po.no}/10 invoiced and paid with no receipt, same "
         "vendor, material and quantity, receipt date fits the second order.")
    x = tag("B3")
    case("B-3", "receipt booked to the wrong line, order not yet invoiced",
         f"`goods_receipts` {x.gr2.no} on order {x.po.no} position 10 with the material of position 30.",
         "60 boxes of position 30 received on position 10 (already complete and invoiced) and valued at the "
         "price of position 10.",
         f"Q1: recorded open item NVK 89,400.00 on position 10; true open item NVK 53,400.00 on position 30; "
         f"overstatement NVK {m(delta['B3'])} (EUR {eur(delta['B3'])}).",
         "`mat_no` of the receipt row is the material of position 30; position 10 over-received; amount is "
         "quantity times the price of position 10.")
    x = tag("C1")
    case("C-1", "currency slip on a purchase order",
         f"`po_header` {x.po.no}: `cur` NVK; vendor {x.po.vend} {vname(x.po.vend)} is a EUR vendor; receipt "
         f"{x.gr.no}.",
         "The order was entered in NVK with the EUR prices (7,450 and 660 per unit). The receipt of 9 December "
         "was valued at NVK 36,400.00 instead of EUR 36,400.00.",
         f"Q1: open item understated by NVK {m(-delta['C1'])} (EUR {eur(-delta['C1'])}); true value NVK "
         f"{m(36400_00 - delta['C1'])} at the December booking rate. Not invoiced by year end.",
         "Vendor master currency EUR against order currency NVK; material master price in EUR equals the order "
         "price digit for digit; all other orders of the vendor are in EUR.")
    x = tag("R3")
    p = pay_of[x.inv.seq]
    case("C-2", "currency slip on a vendor invoice",
         f"`inv_header` {x.inv.no}: `cur` EUR, gross {m(gross_of(x.inv))}; vendor {x.inv.vend} "
         f"{vname(x.inv.vend)} is a domestic NVK vendor, order {x.po.no} is in NVK; payment {p.doc}: "
         f"NVK {m(p.amt)}.",
         "The invoice was entered with currency EUR; the amount is in NVK.",
         f"Ledger: vendor account and clearing account carry NVK {m(x.inv.lc)} instead of "
         f"{m(gross_of(x.inv))} gross. Q2: this is one of the group (a) invoices; its true amount is NVK "
         f"{m(gross_of(x.inv))}, not EUR. Q1: no effect on credit lines (debit line, no receipt).",
         "Vendor and order currency NVK, payment in NVK with the same digits, 20 % domestic tax on a 'EUR' invoice.")
    x = tag("D1")
    case("D-1", "manual clearing of an item whose invoice then arrived",
         f"`gl_lines` journal {x.mj.no} (31.10.), order {x.po.no}/10; receipt {x.gr.no}; invoice {x.inv.no} "
         f"posted {x.inv.post.isoformat()}.",
         "The full value of a receipt was cleared against price differences although the invoice was merely "
         "late. When the invoice came, the clearing was not reversed.",
         f"Debit balance NVK {m(br[(x.po.key, 10)])} on the clearing account (net balance understated), "
         "price differences overstated by the same. Q1 credit lines: none. Far above both limits.",
         "Order line with receipt, invoice and a manual clearing: three legs, balance not zero.")
    x = tag("D2")
    case("D-2", "manual clearing posted to the wrong account",
         f"`gl_lines` journal {x.mj.no} (30.06.), order {x.po.no}/10.",
         "The remainder of a free over-delivery (40 rolls) was cleared with a debit on 1410 inventory instead "
         "of 2810.",
         f"Q1: false open item NVK {m(delta['D2'])} stays on 2810; inventory overstated.",
         "Journal text and assignment name a clearing; the debit line sits on 1410; the order line stays open "
         "with exactly this amount.")
    x = tag("D3")
    case("D-3", "manual clearing without reference to an order",
         f"`gl_lines` journal {x.mj.no} (30.09.): one debit on 2810, NVK {m(rec_unassigned)}, empty assignment; "
         f"belongs to {pono('D3a')}/10, {pono('D3a')}/20 and {pono('D3b')}/10.",
         "Three legitimate small remainders were cleared in one line without order reference.",
         f"Q1: by order line the three remainders stay open (false open items NVK {m(delta['D3'])}); the "
         "account total is right.",
         "The amount equals the sum of exactly these three old remainders (318.00 + 742.50 + 1,126.40).")
    x = tag("D4")
    case("D-4", "manual clearing posted with the wrong sign",
         f"`gl_lines` journal {x.mj.no} (30.05.), order {x.po.no}/10.",
         "The remainder of a free over-delivery (20 rolls, NVK 2,236.00) was credited to 2810 instead of debited.",
         f"Q1: false open item NVK {m(delta['D4'])} (twice the remainder).",
         "After the journal the line balance is twice the remainder instead of zero.")
    x = tag("D5")
    case("D-5", "manual clearing with transposed digits",
         f"`gl_lines` journal {x.mj.no} (31.10.), order {x.po.no}/10.",
         "Remainder NVK 1,384.20, cleared NVK 1,348.20.",
         f"Q1: false open item NVK {m(delta['D5'])}. Trivial.",
         "Residual of 36.00 on a line that was meant to be cleared.")
    ic_2815 = sum(-x for x in rec_2815_lines.values() if x < 0)
    case("E-1", "mapping gap: new account missing in the mapping sheet",
         "`acct_mapping.xlsx`: no row for local account 2815.",
         "Account 2815 (clearing account for group deliveries, in use since 1 July) was never added to the "
         "sheet copied from the old version.",
         f"Any figure built through group accounts loses the whole of 2815 (net balance NVK "
         f"{m(rec_acct['2815'])} at year end). All open items of the group supply company, true NVK "
         f"{m(true_ic)} (EUR {eur(true_ic)}), have their credit leg on 2815. Because group orders invoiced "
         "before 1 July were debited on 2810 and received on 2815, neither account means anything alone.",
         "Anti-join of posted accounts against the mapping on the posting date.")
    n695 = sum(1 for r in Tr.gl if r.acct == "6950" and g.CUT <= r.post < g.D(2025, 8, 1))
    s695 = sum(r.amt for r in Tr.gl if r.acct == "6950" and g.CUT <= r.post < g.D(2025, 8, 1))
    case("E-2", "mapping gap: one month without a valid row",
         "`acct_mapping.xlsx`: account 6950, old row ends 30.06.2025, new row starts 01.08.2025.",
         "The new row has the wrong start date.",
         f"{n695} ledger lines on 6950 in July 2025 (net NVK {m(s695)}) have no group account. No effect on "
         "the three answers.",
         "Validity intervals per account do not cover July.")
    for cid, t, extra in (("F-1", "F1", "Not invoiced at year end."),
                          ("F-2", "F2", "Invoice and payment for the single delivery are in order; the "
                           "second receipt has been open since February.")):
        x = tag(t)
        case(cid, "goods receipt posted twice",
             f"`goods_receipts` {x.gr.no} and {x.dup.no}, order {x.po.no}, same delivery note `{x.gr.dn}`.",
             "One delivery was received twice by two warehouse users; there is no reversal.",
             f"Q1: false open item NVK {m(delta[t])} (EUR {eur(delta[t])}). {extra} Q3: received volume "
             "doubled for this order.",
             "Same order line, same delivery note number and date, same quantity; received quantity is twice "
             "the order quantity.")
    x = tag("H1")
    case("H-1", "unit slip on a vendor invoice",
         f"`inv_lines` {x.inv.no}: quantity 18000 with unit BOX; order {x.po.no}/10 is 36 BOX = 18,000 PCE.",
         "The quantity in pieces was entered with the order unit.",
         f"The system saw 18,000 boxes invoiced against 36 received and posted a debit of NVK "
         f"{m(br[(x.po.key, 10)])} on the clearing account against price differences. Q2: looks paid without "
         "receipt; it is not. Q1 credit lines: none.",
         "Net amount / quantity is 1/500 of the order price; the vendor always bills in pieces.")

    w("## Seeded cases, kind 3 - the data cannot decide\n")
    x = tag("K3")
    case("K3-1", "large December write-off on the clearing account",
         f"`gl_lines` journal {x.mj.no} (19.12.), order {x.po.no} positions 10 and 20, receipt {x.gr.no} of "
         "9 September, no invoice.",
         "Nothing in the data says whether the vendor will still invoice. Generator truth: the vendor's "
         "invoice arrives in January 2026; the liability exists.",
         f"Q1: NVK {m(k3)} (EUR {eur(k3)}) - the width of the range.",
         "It looks like every other clearing journal. Arguments for keeping the liability: far above both "
         "limits, full order value rather than a remainder, no credit note, vendor invoiced all other "
         "orders. None is proof.")
    w("### K3-2 - laboratory orders paid without a receipt\n")
    w(f"- **Records:** invoices {tag('K4a').inv.no} (order {pono('K4a')}) and {tag('K4b').inv.no} (order "
      f"{pono('K4b')}).")
    w("- **Why undecidable:** the handover note says laboratory deliveries go straight to the lab and the "
      "receipt is sometimes never booked. Whether these goods arrived was never recorded.")
    w("- **Effect:** Q2 group (c). Both are 'paid without recorded receipt'; whether a control failed or "
      "only a booking is unknown.\n")
    x = tag("R2")
    p = pay_of[x.inv.seq]
    w("### K3-3 - invoice and payment disagree on the amount\n")
    w(f"- **Records:** invoice {x.inv.no} gross NVK {m(gross_of(x.inv))}; payment {p.doc} NVK {m(p.amt)}.")
    w("- **Why undecidable:** two digits are transposed in one of the two records; there is no bank "
      "statement in the delivery. Generator truth: the invoice is right.")
    w(f"- **Effect:** Q2 amount of this invoice is NVK {m(min(p.amt, gross_of(x.inv)))} or "
      f"{m(max(p.amt, gross_of(x.inv)))}.\n")
    w("### K3-4 - promised delivery date: never recorded before July, overwritten after\n")
    w(f"- **Records:** `po_lines.dlv_dt` empty for all orders before 1 July; {len(Wr.k7)} later lines "
      "overwritten (listed under Question 3).")
    w("- **Effect:** Q3 is answerable only for orders from 1 July, and there only against the last agreed "
      "date.\n")
    w("### K3-5 - one local account mapped to two group accounts\n")
    w("- **Records:** `acct_mapping.xlsx`, account 1450: two rows valid from 01.07.2025, group accounts "
      "120500 and 120150, entered by two different users.")
    w("- **Why undecidable:** neither row has an end date, and the manual extract does not say which group "
      "account takes goods in transit from group companies.")
    w("- **Effect:** none on the three answers; the year-end reclassification of goods in transit cannot be "
      "assigned to one group account.\n")

    # ------------------------------------------------------------ kind 1
    w("## Kind 1 - correct business events that look like errors\n")
    w("All of these are in the clean base and are consistent. A rule that flags them is wrong. "
      "Counts are order lines.\n")
    for cat, ks in sorted(Wr.k1.items()):
        ks = sorted(set(ks))
        lst = ", ".join(lref(k) for k in ks) if len(ks) <= 70 else "(not listed)"
        w(f"- **{cat}** - {len(ks)}: {lst}")
    mj_ok = sum(1 for e in Wt.ev if e.k == "MJ")
    w(f"- **correct manual clearing journals** - {mj_ok} in the true world; in the delivered data all manual "
      "clearings look the same.")
    w("- **opening items** - receipts and invoices of November/December 2024 on orders still moving in 2025; "
      "ledger document type SV on 1 January 2025.")
    w("- **goods in transit reclassification** - 30 June (reversed 1 July) and 31 December, group order lines, "
      "document type SA, same look as the clearing journals.")
    w("- **two clearing accounts** - group order lines with one leg on 2810 (before 1 July) and one on 2815.")
    w("- **two numbering schemes** - documents from 1 July carry the new numbers, also against old orders; the "
      "assignment field changes format with the posting date.")
    w("- **sign conventions** - receipts and credit notes carry positive quantities and amounts; movement type "
      "and document type give the direction; in `payments` credit notes are negative.")
    w("- **exchange differences** - EUR receipts and invoices are booked at different monthly rates; the system "
      "posts the difference to 6950 (the local instruction still says 6900).")
    w("- **recurring invoices** - rent, leasing, cleaning and security are the same amount every month from "
      "the same vendor with different references; not duplicates.")
    w("- **mapping change** - several local accounts map to a different group account from 1 July; the first "
      "half-year is not restated.")
    w("- **document contradictions** - clearing limit NVK 2,500 (local) against EUR 150 (group); payment "
      "without receipt allowed locally on written confirmation, forbidden by the group manual; the local "
      "instruction describes the old numbers, one clearing account, account 6900 and an unused delivery date.\n")

    w("## Deliberately not in this key (ordinary noise)\n")
    w("Vendor names spelled differently in `payments.payee`; city names in capitals; empty buyer, cost "
      "centre, e-mail, ABC indicator and text fields; lower-case units and delivery note numbers; missing or "
      "'w/o DN' delivery note numbers; stray spaces around vendor references; double spaces and capitals in "
      "material texts; free-text remarks on receipts and invoice headers; varying wording of journal texts; "
      "different date formats between files; gaps in the document number ranges; cent differences from "
      "rounding posted as 'Diff. GR/IR'. None of these marks or hides a seeded case.\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
