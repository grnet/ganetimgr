from django.core.management.base import BaseCommand
from ganeti.models import Cluster


class Command(BaseCommand):
    help = "Updates cache cluster instances for specific/all clusters"

    @staticmethod
    def add_arguments(parser):
        parser.add_argument("clusters", nargs="*")
        parser.add_argument("seconds", nargs="?", type=int)

    @staticmethod
    def fetch_clusters(cluster_hostnames=None):
        if not cluster_hostnames:
            return Cluster.objects.all()
        return Cluster.objects.filter(hostname__in=cluster_hostnames)

    @staticmethod
    def refresh(cluster, seconds):
        if seconds:
            cluster.refresh_instances(seconds=seconds)
            cluster.refresh_nodes(seconds=seconds)
        else:
            cluster.refresh_instances()
            cluster.refresh_nodes()

    def handle(self, *args, **options):
        for cluster in self.fetch_clusters(options.get("clusters")):
            print("Refreshing cache for cluster: {0}".format(cluster))
            self.refresh(cluster, options.get("seconds"))