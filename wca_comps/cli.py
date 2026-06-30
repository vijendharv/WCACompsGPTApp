"""Command-line entrypoint that wires the modules together."""

from __future__ import annotations

import argparse
import os
import sys

from .competitions import CompetitionService
from .config import (
    DEFAULT_PERSON_NAME,
    DEFAULT_WCA_ID,
    RESEND_API_KEY_ENV,
    RESEND_API_KEY_FALLBACK,
)
from .networking import WCAClient, WCAApiError
from .notify import EmailError, send_email
from .registrations import RegistrationService
from .report import build_assessments, render_html, render_text
from .errors import InputValidationError
from .validation import parse_from_date, select_regions, validate_wca_id


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find upcoming WCA competitions in U.S. states and Canadian "
            "provinces/territories and check whether a competitor is registered."
        )
    )
    parser.add_argument(
        "--region",
        action="append",
        dest="regions",
        help=(
            "State, province, or territory name/postal abbreviation to search. "
            "Repeat for multiple regions; defaults to Washington, Oregon, and "
            "British Columbia."
        ),
    )
    parser.add_argument(
        "--wca-id", default=DEFAULT_WCA_ID, help="WCA ID to check (e.g. 2023VONT01)"
    )
    parser.add_argument(
        "--name", default=DEFAULT_PERSON_NAME, help="Display name for the report"
    )
    parser.add_argument(
        "--from-date",
        default=None,
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
        wca_id = validate_wca_id(args.wca_id)
        start_from = parse_from_date(args.from_date)
        regions = select_regions(args.regions)
    except InputValidationError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 2

    client = WCAClient()
    competition_service = CompetitionService(client)
    registration_service = RegistrationService(client)

    try:
        assessments = build_assessments(
            competition_service,
            registration_service,
            regions,
            wca_id,
            start_from,
        )
    except WCAApiError as exc:
        print(f"WCA API error: {exc}", file=sys.stderr)
        return 1

    report = render_text(assessments, args.name, wca_id)
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
        subject = f"WCA comps {start_from.isoformat()} - {args.name}"
        html = render_html(assessments, args.name, wca_id)
        try:
            send_email(subject, report, args.email_to, api_key, html=html)
        except EmailError as exc:
            print(f"Email failed: {exc}", file=sys.stderr)
            return 1
        print(f"Emailed report to {args.email_to}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
