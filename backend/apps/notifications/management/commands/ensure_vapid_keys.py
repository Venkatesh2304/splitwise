from django.core.management.base import BaseCommand
from apps.notifications import keys

class Command(BaseCommand):
    help = "Creates the web-push (VAPID) key if it doesn't exist yet. Never replaces an existing key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--subject",
            help="Contact for push services, e.g. mailto:you@example.com (stored; can be changed later).",
        )

    def handle(self, *args, **options):
        subject = options.get("subject")
        if subject and not subject.startswith(("mailto:", "https://")):
            self.stderr.write(self.style.ERROR("--subject must start with mailto: or https://"))
            return
        created = keys.ensure(subject)
        loaded = keys.load()
        self.stdout.write(self.style.SUCCESS(
            ("Created" if created else "Kept existing") + f" push key. Contact: {loaded.subject}"
        ))
