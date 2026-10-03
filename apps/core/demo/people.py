"""Demo organisation: a ~15-person small business with a 3-person IT team.

Fictional people and company. Passwords are not stored here: see passwords.py
(HELPLY_DEMO_PASSWORD in the local .env file). Never load this on a production database.
"""

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

GROUP_MEMBERS = {
    "Service Desk": ["tom", "tina", "sam"],
    "Network & Infrastructure": ["tina"],
    "Applications": ["tom"],
}

# The demo asset register lives in assets.py.
