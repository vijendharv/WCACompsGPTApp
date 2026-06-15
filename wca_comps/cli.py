"""Command-line entrypoint that wires the modules together."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from .competitions import CompetitionService
from .config import (
    DEFAULT_PERSON_NAME,
    DEFAULT_WCA_ID,
    REGIONS,
    RESEND_API_KEY_ENV,
    RESEND_API_KEY_FALLBACK,
)
from .networking import WCAClient, WCAApiError
from .notify import EmailError, send_email
from .registrations import RegistrationService
from .report import build_assessments, render_html, render_text


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find upcoming WCA competitions in Washington, Oregon and British "
            "Columbia and check whether a given competitor is registered."
        )
    )
    parser.add_argument(
        "--wca-id", default=DEFAULT_WCA_ID, help="WCA ID to check (e.g. 2023VONT01)"
    )
    parser.add_argument(
        "--name", default=DEFAULT_PERSON_NAME, help="Display name for the report"
    )
    parser.add_argument(
        "--from-date",
        default=date.today().isoformat(),
        help="Only consider competitions starting on/after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--email-to",
        default=None,
        help=(
            "If set, also email the report to this address via Resend. "
            f"Requires the {RESEND_API_KEY_ENV} environment variable."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        start_from = date.fromisoformat(args.from_date)
    except ValueError:
        print(f"Invalid --from-date: {args.from_date}", file=sys.stderr)
        return 2

    client = WCAClient()
    competition_service = CompetitionService(client)
    registration_service = RegistrationService(client)

    try:
        assessments = build_assessments(
            competition_service,
            registration_service,
            REGIONS,
            args.wca_id,
            start_from,
        )
    except WCAApiError as exc:
        print(f"WCA API error: {exc}", file=sys.stderr)
        return 1

    report = render_text(assessments, args.name, args.wca_id)
    print(report)

    if args.email_to:
        api_key = os.environ.get(RESEND_API_KEY_ENV) or RESEND_API_KEY_FALLBACK
        if not api_key or api_key == "paste-your-resend-api-key-here":
            print(
                f"--email-to was given but no Resend API key is set "
                f"(set {RESEND_API_KEY_ENV} or RESEND_API_KEY_FALLBACK).",
                file=sys.stderr,
            )
            return 2
        subject = f"WCA comps {args.from_date} - {args.name}"
        html = render_html(assessments, args.name, args.wca_id)
        try:
            send_email(subject, report, args.email_to, api_key, html=html)
        except EmailError as exc:
            print(f"Email failed: {exc}", file=sys.stderr)
            return 1
        print(f"Emailed report to {args.email_to}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
