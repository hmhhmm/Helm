"""CFO brief (PDF). Everything on the page comes from the simulation and is labelled synthetic."""
from io import BytesIO

from reportlab.graphics.shapes import Drawing, Line, Polygon, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from helm import views
from helm.fmt import fdate, pct, rm
from helm.models import Receipt, Proposal
from datetime import date, timedelta

VERDICT_LABEL = {"ALLOW": "Released", "HOLD": "Waiting for cash", "ESCALATE": "Needs the owner", "DENY": "Blocked by rule"}
VERDICT_COLOR = {"ALLOW": "#0B7A45", "HOLD": "#9A5B00", "ESCALATE": "#2457D6", "DENY": "#C23B2E"}


def _chart(rng: dict, key: str, width: float, height: float) -> Drawing:
    d = Drawing(width, height)
    p10, p90, p50 = rng[key]["p10"], rng[key]["p90"], rng[key]["p50"]
    n = len(p50)
    lo = min(min(p10), rng["min_balance"]) - 5000
    hi = max(p90) + 5000
    x = lambda i: 30 + (width - 40) * i / (n - 1)
    y = lambda v: 14 + (height - 24) * (v - lo) / (hi - lo)
    pts = [(x(i), y(p90[i])) for i in range(n)] + [(x(i), y(p10[i])) for i in reversed(range(n))]
    d.add(Polygon([c for pt in pts for c in pt], fillColor=colors.HexColor("#D9CFF5"), strokeColor=None))
    for i in range(n - 1):
        d.add(Line(x(i), y(p50[i]), x(i + 1), y(p50[i + 1]), strokeColor=colors.HexColor("#6E4BD8"), strokeWidth=1.5))
    d.add(Line(30, y(rng["min_balance"]), width - 10, y(rng["min_balance"]), strokeColor=colors.HexColor("#C23B2E"), strokeDashArray=[3, 2]))
    d.add(String(32, y(rng["min_balance"]) + 2, f"Minimum {rm(rng['min_balance'])}", fontSize=7, fillColor=colors.HexColor("#C23B2E")))
    d.add(String(30, 2, rng["days"][0], fontSize=7))
    d.add(String(width - 60, 2, rng["days"][-1], fontSize=7))
    return d


def build_pdf(session: Session) -> bytes:
    today = views.sim_today(session)
    t = views.today_view(session)
    rng = views.latest_range(session)
    pay = views.payments_view(session)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Helm CFO brief (synthetic demo data)", author="Helm")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.HexColor("#5B6170"))
    el = [
        Paragraph("Helm CFO brief", h1),
        Paragraph(f"Warisan Printing Sdn Bhd (fictional) &middot; week to {fdate(today)} {today.year} &middot; <b>Synthetic demo data</b> &middot; Payments via Demo bank", small),
        Spacer(1, 6),
        Paragraph(t["headline"]["en"], body),
        Spacer(1, 6),
    ]
    kpi = Table([[
        Paragraph(f"<b>{rm(t['cash_now'])}</b><br/><font size=7>cash now</font>", body),
        Paragraph(f"<b>{t['buffer_days']:.0f} days</b><br/><font size=7>buffer above minimum</font>", body),
        Paragraph(f"<b>{rm(t['low_point']['worst'])}</b><br/><font size=7>bad-case low, {fdate(date.fromisoformat(t['low_point']['worst_date']))}</font>", body),
        Paragraph(f"<b>{pct(t['managed']['p_ok'])}</b><br/><font size=7>chance of staying above {rm(t['min_balance'])} with Helm's plan</font>", body),
    ]], colWidths=[43 * mm] * 4)
    kpi.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E4E4E0")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E4E4E0")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    el += [kpi, Paragraph("Next 90 days if every bill is paid on its due date (median line, 80% range)", h2), _chart(rng, "unmanaged", 170 * mm, 55 * mm),
           Paragraph("With Helm's plan (bills held until it is safe)", h2), _chart(rng, "managed", 170 * mm, 55 * mm)]

    el.append(Paragraph("Paid this week and why", h2))
    paid = [r for r in pay["groups"]["paid"]][:8]
    if paid:
        rows = [["Paid", "Payee", "Amount", "Why"]]
        receipts = {r.proposal_id: r for r in session.execute(select(Receipt)).scalars()}
        for r in paid:
            ex = receipts.get(r["proposal_id"])
            rows.append([fdate(date.fromisoformat(r["sent_on"])), r["payee"], rm(r["amount"]), Paragraph((ex.explanation if ex and ex.explanation else r["why"]) or "", small)])
        tb = Table(rows, colWidths=[18 * mm, 40 * mm, 24 * mm, 92 * mm], repeatRows=1)
        tb.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2EFFB")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E4E4E0"))]))
        el.append(tb)
    else:
        el.append(Paragraph("No payments were sent this week.", body))

    el.append(Paragraph("What Helm is holding or asking about", h2))
    open_rows = [r for g in ("statutory", "due_soon", "can_wait") for r in pay["groups"][g] if r["verdict"] in ("HOLD", "ESCALATE", "DENY")]
    if open_rows:
        for r in open_rows[:8]:
            c = VERDICT_COLOR[r["verdict"]]
            rel = f" until {fdate(date.fromisoformat(r['release_on']))}" if r["release_on"] and r["verdict"] == "HOLD" else ""
            el.append(Paragraph(f"<font color='{c}'><b>{VERDICT_LABEL[r['verdict']]}{rel}</b></font> &middot; {r['payee']} {rm(r['amount'])}<br/><font size=8 color='#5B6170'>{r['why']}</font>", body))
            el.append(Spacer(1, 3))
    else:
        el.append(Paragraph("Nothing is on hold.", body))

    chase = views.collections_view(session)["ideas"][:3]
    if chase:
        el.append(Paragraph("Who to chase first", h2))
        for c in chase:
            el.append(Paragraph(f"<b>{c['customer']}</b> &middot; {rm(c['amount_open'])} open<br/><font size=8 color='#5B6170'>{c['why']}</font>", body))
            el.append(Spacer(1, 3))
    el += [Spacer(1, 10), Paragraph(
        "Targets and methods are not results. Every number here comes from a simulation on synthetic data. Helm is a non-custodial decision layer; "
        "payments in this demo go to a mock Demo bank. Mentions of EPF, SOCSO, EIS, PCB, SST and LHDN are context, not compliance claims.", small)]
    doc.build(el)
    return buf.getvalue()
