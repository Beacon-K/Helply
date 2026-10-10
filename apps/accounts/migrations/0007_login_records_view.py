from django.db import migrations

VIEW = """
CREATE VIEW login_records_readable AS
SELECT id,
       username,
       role,
       ip AS ip_address,
       country,
       logged_in_local AS signed_in,
       logged_out_local AS signed_out,
       last_seen_local AS last_activity,
       online_seconds,
       user_agent AS browser
FROM accounts_loginrecord
"""


class Migration(migrations.Migration):
    """A read-only view for anyone opening the database file: local times only, no UTC columns to misread.

    The app never touches it (no model); the table underneath is accounts_loginrecord.
    """

    dependencies = [
        ("accounts", "0006_local_time_columns"),
    ]

    operations = [
        migrations.RunSQL(VIEW, reverse_sql="DROP VIEW IF EXISTS login_records_readable"),
    ]