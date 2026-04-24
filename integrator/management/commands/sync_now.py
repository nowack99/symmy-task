from django.core.management.base import BaseCommand

from integrator.tasks import sync_products


class Command(BaseCommand):
    help = 'Trigger the ERP -> e-shop sync. Runs inline by default; use --async to dispatch to Celery.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--async',
            dest='run_async',
            action='store_true',
            help='Dispatch the task to the Celery broker instead of running inline.',
        )

    def handle(self, *args, **options):
        if options['run_async']:
            result = sync_products.delay()
            self.stdout.write(self.style.SUCCESS(f'Queued task {result.id}'))
            return
        stats = sync_products()
        self.stdout.write(self.style.SUCCESS(f'Sync done: {stats}'))
