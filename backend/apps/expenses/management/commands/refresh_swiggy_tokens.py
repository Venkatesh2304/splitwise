from datetime import datetime, timezone, timedelta

from django.core.management.base import BaseCommand

from apps.users.models import UserProfile
from apps.expenses.swiggy_views import refresh_swiggy_token, swiggy_expires_at


class Command(BaseCommand):
    help = (
        "Refreshes Swiggy access tokens before they expire. Swiggy cannot refresh a token "
        "that has already died, so waiting for a 401 is waiting too long: without this, a "
        "session lasts the token's 5 days and then needs a full sign-in. Refreshed in time, "
        "the 30-day refresh window keeps sliding and the session persists."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold-hours",
            type=float,
            default=48.0,
            help="Refresh tokens expiring within this many hours (default: 48).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Refresh every session regardless of how long it has left.",
        )

    def handle(self, *args, **options):
        threshold = timedelta(hours=options["threshold_hours"])
        force = options["force"]
        now = datetime.now(timezone.utc)

        profiles = UserProfile.objects.exclude(swiggy_refresh_token__isnull=True).exclude(
            swiggy_refresh_token=""
        )

        refreshed = skipped = failed = 0
        for u in profiles:
            if u.swiggy_access_token == "MANUAL_JSON_OVERRIDE":
                continue

            expires_at = swiggy_expires_at(u)
            # An unknown expiry gets refreshed: better one spare call than a session
            # that quietly dies because we could not read its clock.
            due = force or expires_at is None or (expires_at - now) <= threshold
            if not due:
                skipped += 1
                self.stdout.write(f"{u.name}: {self._left(expires_at, now)} left, no action.")
                continue

            if refresh_swiggy_token(u):
                refreshed += 1
                u.refresh_from_db()
                self.stdout.write(self.style.SUCCESS(
                    f"{u.name}: refreshed, now {self._left(swiggy_expires_at(u), now)} left."
                ))
            else:
                failed += 1
                # refresh_swiggy_token clears the session on invalid_grant, so this
                # means a sign-in is genuinely needed.
                self.stdout.write(self.style.WARNING(
                    f"{u.name}: refresh failed — needs to reconnect Swiggy."
                ))

        self.stdout.write(f"Done. refreshed={refreshed} skipped={skipped} failed={failed}")

    @staticmethod
    def _left(expires_at, now):
        if not expires_at:
            return "unknown time"
        delta = expires_at - now
        if delta.total_seconds() <= 0:
            return "no time"
        hours = delta.total_seconds() / 3600
        return f"{hours:.1f}h" if hours < 48 else f"{hours / 24:.1f}d"
