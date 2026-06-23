"""Orchestration + presentation: build assessments and render a report."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from html import escape

from .competitions import CompetitionService
from .config import Region
from .models import CompetitionAssessment
from .registrations import RegistrationService


def _eligibility(comp, reg, state, now) -> tuple[bool, str]:
    """Decide whether the person can still register, with a human reason."""
    if reg.is_registered and reg.status != "deleted":
        return False, f"Already registered ({reg.status})"
    if state == "not_open_yet":
        when = comp.registration_open.date().isoformat() if comp.registration_open else "?"
        return False, f"Registration not open yet (opens {when})"
    if state == "closed":
        return False, "Registration closed"

    # Registration is open and the person is not registered.
    limit = comp.competitor_limit
    count = reg.competitor_count
    if limit is not None and count is not None and count >= limit:
        return True, f"Open but at capacity ({count}/{limit}) - waitlist only"
    if limit is not None and count is not None:
        return True, f"Open - {limit - count} spot(s) left ({count}/{limit})"
    return True, "Open"


def build_assessments(
    competition_service: CompetitionService,
    registration_service: RegistrationService,
    regions: tuple[Region, ...],
    wca_id: str,
    start_from: date,
    now: datetime | None = None,
    max_registration_workers: int = 8,
) -> list[CompetitionAssessment]:
    """Fetch comps in the regions and assess each for the given person."""
    now = now or datetime.now(timezone.utc)
    pairs = competition_service.upcoming_in_regions(regions, start_from)

    assessments: list[CompetitionAssessment] = []
    if not pairs:
        return assessments

    worker_count = max(1, min(max_registration_workers, len(pairs)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        registrations = list(
            executor.map(
                lambda pair: registration_service.check(pair[1].id, wca_id),
                pairs,
            )
        )

    for (region, comp), reg in zip(pairs, registrations):
        state = comp.registration_state(now)
        can_register, reason = _eligibility(comp, reg, state, now)
        assessments.append(
            CompetitionAssessment(
                competition=comp,
                region_name=region.name,
                registration=reg,
                registration_state=state,
                can_register=can_register,
                reason=reason,
            )
        )
    return assessments


def render_text(
    assessments: list[CompetitionAssessment], person_name: str, wca_id: str
) -> str:
    """Render assessments as a readable plain-text report."""
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append(
        f"Upcoming WCA competitions (WA / OR / BC) for {person_name} ({wca_id})"
    )
    lines.append("=" * 78)

    def block(title: str, items: list[CompetitionAssessment]) -> None:
        lines.append("")
        lines.append(f"## {title} ({len(items)})")
        if not items:
            lines.append("  (none)")
            return
        for a in items:
            c = a.competition
            lines.append("")
            lines.append(f"  {c.name}  [{a.region_name}]")
            lines.append(f"    Date        : {c.start_date}"
                         + (f" - {c.end_date}" if c.end_date != c.start_date else ""))
            lines.append(f"    Location    : {c.city} - {c.venue}")
            lines.append(f"    Events      : {', '.join(c.event_ids)}")
            cap = (
                f"{a.registration.competitor_count}/{c.competitor_limit}"
                if c.competitor_limit is not None
                else "n/a"
            )
            lines.append(f"    Competitors : {cap}")
            if c.registration_open:
                lines.append(
                    f"    Reg window  : {c.registration_open.date()} -> "
                    f"{c.registration_close.date() if c.registration_close else '?'}"
                )
            lines.append(f"    Status      : {a.reason}")
            lines.append(f"    Link        : {c.url}")

    registered, can_register, cannot = _group(assessments)

    block("Already registered", registered)
    block("Can register (open, not yet registered)", can_register)
    block("Not currently registerable", cannot)

    lines.append("")
    lines.append("-" * 78)
    lines.append(
        f"Summary: {len(assessments)} comps found | "
        f"{len(registered)} registered | "
        f"{len(can_register)} open to register | "
        f"{len(cannot)} unavailable"
    )
    return "\n".join(lines)


def _group(
    assessments: list[CompetitionAssessment],
) -> tuple[
    list[CompetitionAssessment],
    list[CompetitionAssessment],
    list[CompetitionAssessment],
]:
    """Split assessments into (registered, can_register, cannot)."""
    registered = [
        a
        for a in assessments
        if a.registration.is_registered and a.registration.status != "deleted"
    ]
    can_register = [
        a
        for a in assessments
        if a not in registered and a.can_register
    ]
    cannot = [
        a
        for a in assessments
        if a not in registered and not a.can_register
    ]
    return registered, can_register, cannot


def render_html(
    assessments: list[CompetitionAssessment], person_name: str, wca_id: str
) -> str:
    """Render assessments as a responsive, email-client-safe HTML report."""
    registered, can_register, cannot = _group(assessments)

    def card(a: CompetitionAssessment, accent: str) -> str:
        c = a.competition
        when = escape(c.start_date) + (
            f" &ndash; {escape(c.end_date)}" if c.end_date != c.start_date else ""
        )
        cap = (
            f"{a.registration.competitor_count}/{c.competitor_limit}"
            if c.competitor_limit is not None
            else "n/a"
        )
        rows = [
            ("Date", when),
            ("Location", escape(f"{c.city} - {c.venue}")),
            ("Events", escape(", ".join(c.event_ids))),
            ("Competitors", escape(cap)),
        ]
        if c.registration_open:
            close = c.registration_close.date() if c.registration_close else "?"
            rows.append(
                ("Reg window", f"{escape(str(c.registration_open.date()))} &rarr; {escape(str(close))}")
            )
        rows.append(("Status", escape(a.reason)))
        detail_rows = "".join(
            f'<tr><td style="padding:2px 12px 2px 0;color:#6b7280;'
            f'font-size:13px;white-space:nowrap;vertical-align:top;">{label}</td>'
            f'<td style="padding:2px 0;color:#111827;font-size:13px;">{value}</td></tr>'
            for label, value in rows
        )
        return (
            f'<div style="border:1px solid #e5e7eb;border-left:4px solid {accent};'
            f'border-radius:8px;padding:14px 16px;margin:10px 0;background:#ffffff;">'
            f'<div style="font-size:15px;font-weight:600;color:#111827;margin-bottom:8px;">'
            f'<a href="{escape(c.url)}" style="color:#111827;text-decoration:none;">'
            f'{escape(c.name)}</a>'
            f'<span style="display:inline-block;margin-left:8px;padding:1px 8px;'
            f'border-radius:10px;background:#f3f4f6;color:#6b7280;font-size:11px;'
            f'font-weight:500;">{escape(a.region_name)}</span></div>'
            f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;">{detail_rows}</table></div>'
        )

    def section(title: str, items: list[CompetitionAssessment], accent: str) -> str:
        body = (
            "".join(card(a, accent) for a in items)
            if items
            else '<div style="color:#9ca3af;font-size:13px;font-style:italic;'
            'padding:4px 0;">None</div>'
        )
        return (
            f'<h2 style="font-size:15px;color:#374151;margin:24px 0 4px;'
            f'border-bottom:1px solid #e5e7eb;padding-bottom:6px;">'
            f'{escape(title)} '
            f'<span style="color:#9ca3af;font-weight:400;">({len(items)})</span>'
            f"</h2>{body}"
        )

    summary = (
        f"{len(assessments)} comps &middot; {len(registered)} registered &middot; "
        f"{len(can_register)} open to register &middot; {len(cannot)} unavailable"
    )

    return (
        '<div style="margin:0;padding:0;background:#f9fafb;">'
        '<div style="max-width:640px;margin:0 auto;padding:24px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Helvetica,Arial,sans-serif;">'
        '<h1 style="font-size:20px;color:#111827;margin:0 0 4px;">'
        "Upcoming WCA competitions</h1>"
        f'<div style="color:#6b7280;font-size:13px;margin-bottom:4px;">'
        f"WA / OR / BC &middot; {escape(person_name)} ({escape(wca_id)})</div>"
        f'<div style="color:#6b7280;font-size:12px;margin-bottom:8px;">{summary}</div>'
        f'{section("Already registered", registered, "#10b981")}'
        f'{section("Can register (open, not yet registered)", can_register, "#3b82f6")}'
        f'{section("Not currently registerable", cannot, "#9ca3af")}'
        '<div style="color:#9ca3af;font-size:11px;margin-top:24px;'
        'border-top:1px solid #e5e7eb;padding-top:12px;">'
        "Sent by WCA Competition Finder</div></div></div>"
    )
