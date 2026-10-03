"""Clean-up for data that earlier demo versions created.

Version 1 of the monitoring demo invented five cloud servers. The page now shows only servers people
add themselves, so seed_demo removes those samples (and their asset records). A server is only
removed if it still has the sample name, its sample asset tag and no agent token - a server someone
connected for real is never touched.
"""
SAMPLE_SERVERS = {"web-prod-01", "erp-01", "backup-01", "win-acct-01", "test-01"}


def remove_sample_servers():
    from apps.assets.models import Asset
    from apps.monitoring.models import Server

    samples = Server.objects.filter(name__in=SAMPLE_SERVERS, token_lookup__isnull=True,
                                    asset__asset_tag__startswith="VPS-")
    asset_ids = list(samples.values_list("asset_id", flat=True))
    count = samples.count()
    samples.delete()
    Asset.objects.filter(pk__in=asset_ids).delete()
    return count
