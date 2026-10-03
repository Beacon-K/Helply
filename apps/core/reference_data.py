"""Default reference data shared by the seed commands.

SLA targets are placeholders - confirm the real numbers with the client.
"""

GROUPS = ["Service Desk", "Network & Infrastructure", "Applications"]

# name, owning support group, classifier keywords
CATEGORIES = [
    ("Hardware", "Service Desk",
     "laptop,desktop,computer,pc,printer,print,monitor,screen,display,keyboard,mouse,battery,charger,dock,"
     "webcam,camera,headset,microphone,speaker,blue screen,frozen,freeze,power"),
    ("Network", "Network & Infrastructure",
     "wifi,wi-fi,wireless,vpn,internet,network,connection,ethernet,slow internet,disconnect,disconnecting,offline"),
    ("Account & Access", "Service Desk",
     "password,login,log in,sign in,account,locked,lockout,mfa,authenticator,2fa,access,permission,reset"),
    ("Software", "Applications",
     "install,excel,word,powerpoint,office,crash,crashes,crashing,license,licence,activation,teams,zoom,update,"
     "software,app,application,browser,chrome,edge"),
    ("Email", "Applications",
     "email,e-mail,outlook,mailbox,spam,calendar,inbox,shared mailbox,send,receive,attachment"),
    ("Security", "Service Desk",
     "phishing,phish,suspicious,scam,virus,malware,ransomware,hacked,compromised,stolen,lost,popup,pop-up"),
    ("Files & Storage", "Service Desk",
     "file,folder,onedrive,sharepoint,shared drive,network drive,deleted,recover,restore,sync,disk space,storage"),
    ("Servers & Cloud", "Network & Infrastructure",
     "server,vps,cloud server,virtual machine,vm,website down,site down,aws,azure,hosting,cpu,uptime,rdp,ssh"),
]

SLA = [  # priority, name, response minutes, resolution minutes
    ("P1", "Critical", 15, 4 * 60),
    ("P2", "High", 60, 8 * 60),
    ("P3", "Medium", 4 * 60, 24 * 60),
    ("P4", "Low", 8 * 60, 72 * 60),
]


def ensure_categories():
    """Create any missing support groups / categories. Safe to run repeatedly."""
    from apps.accounts.models import SupportGroup
    from apps.tickets.models import Category

    groups = {name: SupportGroup.objects.get_or_create(name=name)[0] for name in GROUPS}
    categories = {}
    for name, group, keywords in CATEGORIES:
        category, created = Category.objects.get_or_create(
            name=name, defaults={"default_group": groups[group], "keywords": keywords}
        )
        if not created and not category.keywords:
            category.keywords = keywords
            category.save(update_fields=["keywords"])
        categories[name] = category
    return groups, categories
