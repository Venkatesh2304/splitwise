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
        # py_vapid signs only with a mailto: contact, so anything else would break
        # every push at send time rather than here
        if subject and not subject.startswith("mailto:"):
            self.stderr.write(self.style.ERROR("--subject must be a mailto: address, e.g. mailto:you@example.com"))
            return
        created = keys.ensure(subject)
        loaded = keys.load()
        self.stdout.write(self.style.SUCCESS(
            ("Created" if created else "Kept existing") + f" push key. Contact: {loaded.subject}"
        ))
        if loaded.subject == keys.DEFAULT_SUBJECT:
            self.stdout.write(self.style.WARNING(
                "That contact is a placeholder. Set a real one with:\n"
                "  python manage.py ensure_vapid_keys --subject mailto:you@example.com"
            ))
