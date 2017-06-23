from django.core.management.base import BaseCommand
from ganeti.models import Cluster


class Command(BaseCommand):
    help = "Updates cache cluster instances for specific/all clusters"

    def add_arguments(self, parser):
        parser.add_argument("clusters", nargs="*")

    @staticmethod
    def fetch_clusters(cluster_hostnames=None):
        if not cluster_hostnames:
            return Cluster.objects.all()
        return Cluster.objects.filter(hostname__in=cluster_hostnames)

    def handle(self, *args, **options):
        for cluster in self.fetch_clusters(options.get("clusters")):
            print("Refreshing cache for cluster: {0}".format(cluster))
            cluster.refresh_instances()
