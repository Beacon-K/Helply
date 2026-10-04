"""Demo organisation: a 100-person small business with a 4-person IT team.

Fictional people and company. Passwords are not stored here: see passwords.py
(HELPLY_DEMO_PASSWORD in the local .env file). Never load this on a production database.
"""

# Every demo account's address is <username>@helply.work. Those addresses have no mailbox behind them (no MX
# record yet), so demo accounts are created with email notifications OFF: anything emailed there would bounce
# and damage the sending domain. In-app notifications work as usual; whoever gets a real mailbox turns emails
# on from the Notifications page.
EMAIL_DOMAIN = "helply.work"


def email_for(username):
    return f"{username}@{EMAIL_DOMAIN}"

# username, first, last, role, department, job title
USERS = [
    ("alice", "Alice", "Martin", "administrator", "IT", "IT Manager"),
    ("tom", "Tom", "Nguyen", "technician", "IT", "Systems Technician"),
    ("tina", "Tina", "Roy", "technician", "IT", "Network Technician"),
    ("sam", "Sam", "Okafor", "technician", "IT", "Service Desk Technician"),
    ("daniel", "Daniel", "Kim", "employee", "Management", "General Manager"),
    ("emma", "Emma", "Clark", "employee", "Finance", "Accountant"),
    ("mia", "Mia", "Patel", "employee", "Finance", "Payroll Coordinator"),
    ("eric", "Eric", "Singh", "employee", "Sales", "Account Executive"),
    ("lucas", "Lucas", "Bouchard", "employee", "Sales", "Sales Representative"),
    ("olivia", "Olivia", "Brown", "employee", "HR", "HR Generalist"),
    ("liam", "Liam", "Tremblay", "employee", "Operations", "Operations Manager"),
    ("chloe", "Chloe", "Lee", "employee", "Operations", "Purchasing Coordinator"),
    ("sophia", "Sophia", "Chen", "employee", "Marketing", "Marketing Specialist"),
    ("noah", "Noah", "Gagnon", "employee", "Warehouse", "Warehouse Lead"),
    ("ava", "Ava", "Wilson", "employee", "Front Office", "Receptionist"),
]

# 85 more employees so the company has 100 people. Generated from fixed lists (no randomness), so every
# run produces the same usernames, and a username is the first name like the people above.
_FIRST_NAMES = """
Hannah Ethan Isabella Mason Amelia Logan Harper Benjamin Evelyn James Abigail Henry Emily Jacob Ella Owen Grace
Caleb Zoe Nathan Layla Isaac Nora Aaron Maya Adrian Leah Julian Priya Arjun Aisha Omar Fatima Yusuf Mei Wei Hiro
Yuki Sana Ravi Anika Dev Camille Pierre Juliette Mathieu Sofia Mateo Valentina Diego Lucia Marco Elena Andre Naomi
Kofi Amara Tariq Leila Nadia Khalid Ingrid Lars Katarina Dmitri Anya Pavel Tessa Colin Fiona Dylan Megan Brendan
Shauna Kyle Jasmine Marcus Tamara Victor Stella Ruben Alma Felix Greta Oscar
""".split()
_LAST_NAMES = """
Anderson Baker Campbell Dubois Fraser Gill Hamilton Ibrahim Jensen Khan Lavoie Morin Nakamura Olsen Peters Quinn
Roberts Santos Thompson Underwood Vasquez Walker Young Zhang Ahmed Bell Carter Davis Evans Foster Green Hughes
Jackson Kelly Lopez Mitchell Nelson Ortiz Parker Reid Stewart Turner
""".split()
# department, how many to add, job titles handed out in turn
_GROWTH = [
    ("Management", 4, ["Director of Operations", "Director of Finance", "Director of Sales", "Executive Assistant"]),
    ("Finance", 6, ["Accountant", "Accounts Payable Clerk", "Accounts Receivable Clerk", "Financial Analyst", "Bookkeeper"]),
    ("Sales", 12, ["Sales Representative", "Account Executive", "Sales Coordinator", "Inside Sales Representative"]),
    ("HR", 4, ["HR Coordinator", "Recruiter", "Payroll Specialist", "Training Coordinator"]),
    ("Operations", 13, ["Operations Coordinator", "Logistics Planner", "Purchasing Agent", "Quality Inspector", "Production Supervisor"]),
    ("Marketing", 6, ["Content Specialist", "Graphic Designer", "Marketing Coordinator", "Digital Marketer"]),
    ("Warehouse", 17, ["Warehouse Associate", "Forklift Operator", "Shipping Clerk", "Receiving Clerk", "Inventory Controller"]),
    ("Front Office", 4, ["Receptionist", "Office Administrator", "Facilities Coordinator"]),
    ("Customer Service", 19, ["Customer Service Representative", "Support Specialist", "Customer Success Associate", "Team Lead"]),
]


def _grow():
    firsts, lasts = iter(_FIRST_NAMES), 0
    people = []
    for dept, count, titles in _GROWTH:
        for i in range(count):
            first = next(firsts)
            last = _LAST_NAMES[(lasts * 7 + 3) % len(_LAST_NAMES)]
            lasts += 1
            people.append((first.lower(), first, last, "employee", dept, titles[i % len(titles)]))
    return people


USERS += _grow()

GROUP_MEMBERS = {
    "Service Desk": ["tom", "tina", "sam"],
    "Network & Infrastructure": ["tina"],
    "Applications": ["tom"],
}

# The demo asset register lives in assets.py.
