"""Realistic demo tickets for a small business, replayed through the real workflow.

Each scenario is a ticket plus a timeline of steps. Steps are minutes after the
ticket was created. The simulator (simulate.py) replays every step of every
ticket in chronological order with the clock set to that moment, so SLA
timers, breaches, AI triage and the audit trail all come from the real
business code rather than hand-written rows.

Step actions
    ("assign", tech)            supervisor assigns, unless the AI already did
    ("reassign", tech)          supervisor reassigns
    ("category", name)          supervisor sets / corrects the category
    ("start",) ("hold", note) ("resume", note) ("resolve", note)   by the assignee
    ("reopen", note)            by the requester
    ("close",) / ("close", who) requester confirms, or e.g. "alice" closes
    ("cancel", who, note)
    ("reply", who, text)        public comment   (who: "requester", "assignee" or a username)
    ("note", who, text)         internal note
    ("survey", rating, comment) requester's satisfaction rating

`when` is either ("ago", minutes) for live tickets, or ("day", days_ago, "HH:MM")
for history (moved back to the previous weekday if it falls on a weekend).
Text may reference another scenario's ticket number as {key}.
"""
from dataclasses import dataclass, field

H = 60
D = 24 * H


@dataclass
class Scenario:
    requester: str
    title: str
    description: str
    impact: int
    urgency: int
    when: tuple
    steps: list = field(default_factory=list)
    category: str | None = None  # None = employee chose "let Helply decide" (AI triage)
    channel: str = "portal"
    asset: str | None = None
    key: str | None = None


def ago(minutes):
    return ("ago", minutes)


def day(days_ago, hhmm):
    return ("day", days_ago, hhmm)


SCENARIOS = [
    # ------------------------------------------------------------------ history
    Scenario(
        key="internet_outage", requester="daniel", channel="phone", category="Network",
        title="Internet down for the whole office",
        description="Nobody can get online - email, Teams and the booking system are all down. Phones (VoIP) are also dead.",
        impact=1, urgency=1, when=day(20, "08:52"),
        steps=[
            (4, "assign", "tina"),
            (6, "start"),
            (8, "note", "assignee", "Firewall up, WAN1 down. ISP modem shows no sync. Opened case with the ISP."),
            (12, "reply", "assignee", "We're aware the internet is down for the whole office - the provider has an outage in our area. "
                                     "I'm switching the firewall to the LTE backup link. Email and Teams should come back within 10-15 "
                                     "minutes but will be slower, so please avoid large uploads."),
            (27, "note", "assignee", "Failover to LTE backup working (~20 Mbps). VoIP back. Monitoring."),
            (150, "reply", "assignee", "Update: the provider reports a fibre cut nearby. Repair crew on site, estimated 1 hour."),
            (205, "resolve", "Provider repaired a fibre cut; WAN1 back at 12:17 and the firewall failed back from LTE automatically. "
                             "Primary link down ~3h20m; LTE backup restored email/Teams after ~25 min. Follow-up: review the "
                             "backup data plan size in the post-incident review."),
            (240, "close"),
            (241, "survey", 4, "The backup link saved the morning. Would like more frequent updates next time."),
        ],
    ),
    Scenario(
        requester="sophia", title="No internet",
        description="Nothing loads and Teams says I'm offline. Wi-Fi shows connected.",
        impact=2, urgency=1, when=day(20, "08:55"),
        steps=[(9, "cancel", "alice", "Duplicate of {internet_outage} (office-wide outage) - updates will be posted there.")],
    ),
    Scenario(
        requester="noah", title="Warehouse can't reach inventory system",
        description="Scanners and the inventory app say no connection. Can't process any orders.",
        impact=2, urgency=1, when=day(20, "09:01"),
        steps=[(6, "cancel", "alice", "Duplicate of {internet_outage} (office-wide outage).")],
    ),
    Scenario(
        requester="liam", asset="PR-0003",
        title="Label printer offline - can't print shipping labels",
        description="The Zebra label printer in the warehouse shows offline on every PC since this morning. "
                    "We can't print shipping labels and the courier pickup is at 3pm.",
        impact=2, urgency=1, when=day(38, "10:15"),
        steps=[
            (10, "category", "Hardware"),
            (11, "assign", "sam"),
            (20, "start"),
            (22, "reply", "assignee", "On my way to the warehouse now."),
            (45, "note", "assignee", "Printer got a new IP from DHCP after Saturday's power cut (was .45, now .112). Queues still point to the old IP."),
            (62, "resolve", "Label printer received a new IP after the weekend power cut. Updated the printer port on the 3 warehouse "
                            "PCs and created a DHCP reservation so the address can't change again. Test labels printed OK."),
            (95, "close"),
            (96, "survey", 5, "Sorted well before the courier came. Thanks!"),
        ],
    ),
    Scenario(
        requester="ava", asset="DT-0001", category="Hardware",
        title="Front desk PC won't turn on",
        description="The reception computer won't switch on after the weekend. No lights at all. I need it for the visitor sign-in and bookings.",
        impact=2, urgency=1, when=day(33, "08:10"),
        steps=[
            (25, "assign", "sam"),
            (40, "start"),
            (50, "reply", "assignee", "No power light even with a known-good cable - the power supply has most likely failed. "
                                      "I've set you up on a loaner laptop so you can use the booking system in the meantime."),
            (55, "hold", "Waiting for a replacement power supply (ordered, next-day delivery)."),
            (26 * H, "resume", "Replacement power supply delivered."),
            (27 * H, "resolve", "Replaced the failed power supply in the front desk PC. All data intact. Loaner laptop returned to stock."),
            (28 * H, "close"),
            (28 * H + 2, "survey", 3, "The loaner helped, but it took more than a day to get my own PC back."),
        ],
    ),
    Scenario(
        requester="olivia", category="Account & Access",
        title="Access to HR Payroll folder for Mia",
        description="Please give Mia Patel read access to the HR > Payroll folder on the S: drive. "
                    "She's taking over payroll processing from next week. Daniel has approved this.",
        impact=3, urgency=3, when=day(29, "11:20"),
        steps=[
            (90, "assign", "tom"),
            (120, "start"),
            (125, "note", "assignee", "Manager approval confirmed by Daniel via Teams at 13:15."),
            (140, "reply", "assignee", "Done - Mia has read access to S:\\HR\\Payroll. She may need to sign out and back in to see it."),
            (141, "resolve", "Added Mia Patel to the HR-Payroll-Read security group (approved by Daniel Kim)."),
            (24 * H, "close"),
            (24 * H + 1, "survey", 5, ""),
        ],
    ),
    Scenario(
        requester="sophia",
        title="Adobe Creative Cloud licence for new designer",
        description="Our new designer starts on the 15th and needs Photoshop, Illustrator and InDesign on their laptop.",
        impact=3, urgency=3, when=day(27, "14:05"),
        steps=[
            (60, "category", "Software"),
            (61, "assign", "tom"),
            (4 * H, "start"),
            (4 * H + 5, "reply", "assignee", "Creative Cloud is a paid monthly subscription, so I need your manager's approval for the "
                                             "cost before I can buy the licence. Could you get Daniel's OK and reply here?"),
            (4 * H + 6, "hold", "Waiting for cost approval from the requester's manager."),
            (2 * D, "reply", "requester", "Daniel approved it this morning (email forwarded to you)."),
            (2 * D + 30, "resume", "Approval received."),
            (2 * D + 90, "resolve", "Purchased 1 Creative Cloud All Apps licence and assigned it to the new designer's account. "
                                    "Apps will be installed during onboarding."),
            (3 * D, "close"),
            (3 * D + 1, "survey", 4, ""),
        ],
    ),
    Scenario(
        requester="mia",
        title="Email from Daniel asking me to buy gift cards?",
        description="I got an email that looks like it's from Daniel asking me to buy 5 x $200 Apple gift cards for a client "
                    "and send him the codes today. The address is daniel.kim.office@gmail.com. It seems odd - is this real?",
        impact=2, urgency=1, when=day(24, "09:31"),
        steps=[
            (5, "category", "Security"),
            (6, "assign", "tina"),
            (8, "start"),
            (10, "reply", "assignee", "Good catch - this is a scam (CEO impersonation). Don't reply and don't buy anything. "
                                      "Please use the Report button in Outlook on that message. I'm checking whether others got it too."),
            (35, "note", "assignee", "Same message delivered to 6 mailboxes (Finance, HR, Front Office). Purged from all mailboxes, "
                                     "sender blocked. Message trace: no replies sent."),
            (40, "resolve", "Confirmed gift-card phishing impersonating the GM. Removed from 6 mailboxes and blocked the sender. "
                            "Nobody replied. Sent a staff reminder linking the KB article 'How to recognize and report phishing emails'."),
            (3 * H, "close"),
            (3 * H + 1, "survey", 5, "Really quick response, thank you."),
        ],
    ),
    Scenario(
        requester="noah", asset="NW-0002",
        title="Wi-Fi drops near the loading dock",
        description="Our handheld scanners lose Wi-Fi at the loading dock and the back racks, so scans don't upload until we walk "
                    "back to the office. It's been getting worse for a couple of weeks.",
        impact=2, urgency=2, when=day(22, "13:40"),
        steps=[
            (30, "category", "Network"),
            (31, "assign", "tina"),
            (3 * H, "start"),
            (3 * H + 5, "reply", "assignee", "I'll come by tomorrow morning with a Wi-Fi analyser to map the signal."),
            (20 * H, "note", "assignee", "Survey: -82 dBm at the dock, single AP in the office corner. Need a second AP near the dock. "
                                         "Liam approved the purchase."),
            (20 * H + 10, "hold", "Waiting for a second access point to be delivered."),
            (4 * D, "resume", "Access point delivered."),
            (4 * D + 3 * H, "resolve", "Installed a second access point above the loading dock and tuned channels/power on both. "
                                       "Signal at the dock now -58 dBm; scanners upload in real time."),
            (5 * D, "close"),
            (5 * D + 1, "survey", 4, "Much better now. Took a while to get the part though."),
        ],
    ),
    Scenario(
        requester="daniel", channel="phone",
        title="Lost company iPhone in a taxi",
        description="I think I left my company iPhone in a taxi on the way back from the airport about 20 minutes ago.",
        impact=2, urgency=1, when=day(16, "18:40"), asset="PH-0001",
        steps=[
            (15, "category", "Security"),
            (16, "assign", "tina"),
            (20, "start"),
            (26, "note", "assignee", "Revoked sessions, reset password, sent remote lock with a contact message. "
                                     "Find My shows the device at the taxi company's depot."),
            (30, "reply", "assignee", "Your phone is locked remotely and your work account is signed out on it, so company data is safe. "
                                      "Find My shows it at the taxi company's depot - could you give them a call? "
                                      "I've texted a temporary password to your personal number."),
            (14 * H, "reply", "requester", "Got it back from the taxi company this morning."),
            (14 * H + 30, "resolve", "Phone recovered. Removed the remote lock and the user signed back in. "
                                     "Sign-in logs show no unauthorised access."),
            (D, "close"),
            (D + 1, "survey", 5, ""),
        ],
    ),
    Scenario(
        requester="eric",
        title="Account locked after password reset",
        description="I reset my password this morning and now my account is locked, I cannot login to anything.",
        impact=2, urgency=1, when=day(15, "08:47"),
        steps=[
            (10, "start"),
            (14, "reply", "assignee", "Your account was locked by repeated sign-in attempts from your phone - it still had the old "
                                      "password. I've unlocked it; please update the password in the Outlook app on your phone."),
            (15, "resolve", "Unlocked account. Lockout source: old password saved in the Outlook mobile app. User updated the phone."),
            (2 * H, "close"),
            (2 * H + 1, "survey", 5, ""),
        ],
    ),
    Scenario(
        requester="lucas", asset="LT-0004", category="Hardware",
        title="Laptop screen cracked",
        description="I dropped my laptop at a client's office and the screen is cracked - the left half is black. "
                    "I can still use it with an external monitor. I'm travelling again on Thursday.",
        impact=3, urgency=2, when=day(19, "16:20"),
        steps=[
            (40, "assign", "sam"),
            (17 * H, "start"),
            (17 * H + 5, "reply", "assignee", "Please drop it at IT this morning. I'll give you a loaner with your OneDrive files synced "
                                              "so you're ready for Thursday."),
            (18 * H, "hold", "Laptop sent for screen repair; user working on loaner LT-0011."),
            (6 * D, "resume", "Repaired laptop returned by the repair centre."),
            (6 * D + 60, "resolve", "Screen replaced under accidental damage cover. Laptop returned to user; loaner LT-0011 back in stock."),
            (7 * D, "close"),
        ],
    ),
    Scenario(
        requester="chloe", asset="LT-0008",
        title="Excel crashes opening the inventory workbook",
        description="Excel crashes every time I open the Inventory Forecast workbook from the shared drive. Other files open fine.",
        impact=3, urgency=2, when=day(17, "10:05"),
        steps=[
            (2 * H, "start"),
            (2 * H + 10, "reply", "assignee", "Could you try opening it now? I've disabled an old PDF add-in that was crashing Excel."),
            (3 * H, "reply", "requester", "Opens now, thanks!"),
            (3 * H + 5, "resolve", "Disabled a faulty third-party COM add-in (legacy PDF exporter) that crashed Excel on large workbooks."),
            (D + 2 * H, "reopen", "It's crashing again this morning with the same file."),
            (D + 3 * H, "note", "assignee", "Add-in re-enabled itself after last night's Office update. Uninstalling it completely."),
            (D + 4 * H, "resolve", "Uninstalled the legacy PDF add-in (it re-enabled after an Office update) and ran Office Quick Repair. "
                                   "Workbook now opens reliably - tested 3 times with the user."),
            (2 * D, "close"),
            (2 * D + 1, "survey", 4, "Fixed now, but I had to report it twice."),
        ],
    ),
    Scenario(
        requester="emma",
        title="QuickBooks can't find the company file - month-end",
        description="QuickBooks says it can't find the company file on the server. It worked on Friday. "
                    "It's month-end and we need to post invoices today.",
        impact=2, urgency=1, when=day(31, "08:30"),
        steps=[
            (12, "category", "Software"),
            (13, "assign", "tom"),
            (20, "start"),
            (25, "reply", "assignee", "Looking at it now - a remote support request will pop up on your screen."),
            (70, "note", "assignee", "Weekend Windows update on the file server reset the QuickBooks Database Server Manager service "
                                     "to Manual; service not running."),
            (80, "resolve", "The QuickBooks database service on the file server was stopped after the weekend update. Started it and "
                            "set it to start automatically. Company file opens for all Finance users."),
            (3 * H, "close"),
            (3 * H + 1, "survey", 5, "Saved month-end!"),
        ],
    ),
    Scenario(
        requester="ava", category="Network",
        title="Guest Wi-Fi password for visitors",
        description="A visitor asked for the guest Wi-Fi password and I don't have the current one.",
        impact=3, urgency=3, when=day(26, "09:15"),
        steps=[
            (35, "assign", "sam"),
            (40, "start"),
            (42, "reply", "assignee", "The guest network is 'Guest-WiFi'. I've put a fresh printed card with the password in the front "
                                      "desk drawer. It changes monthly - I'll drop off the new card each month."),
            (43, "resolve", "Provided a guest Wi-Fi card at the front desk and added reception to the monthly password rotation list."),
            (3 * H, "close"),
        ],
    ),
    Scenario(
        requester="olivia", category="Account & Access",
        title="New hire starting Monday - Jordan Blake (Sales)",
        description="New hire: Jordan Blake, Sales Representative, starts Monday 9am. Needs a laptop, email, Teams, the CRM and "
                    "access to the Sales shared folder. Manager: Eric Singh.",
        impact=3, urgency=2, when=day(12, "10:30"),
        steps=[
            (60, "assign", "sam"),
            (3 * H, "start"),
            (3 * H + 5, "note", "assignee", "Following the onboarding runbook. Account jordan.blake created, M365 licence assigned, "
                                            "Sales groups added. New laptop from stock being prepared."),
            (D, "reply", "assignee", "All set for Monday: account and laptop are ready. I'll meet Jordan at 9:15 to hand over the "
                                     "laptop and set up MFA."),
            (2 * D + 22 * H, "resolve", "Onboarded Jordan Blake: account, licence, Sales groups, CRM access, laptop handed over, "
                                        "MFA registered, walkthrough of the Helply portal and knowledge base."),
            (3 * D + 2 * H, "close"),
            (3 * D + 2 * H + 1, "survey", 5, "Smooth first day for Jordan."),
        ],
    ),
    Scenario(
        requester="liam", category="Account & Access",
        title="Offboarding: Mark Davis leaves Friday",
        description="Mark Davis (Operations) leaves on Friday - his last day ends at 5pm. Please give me access to his email for "
                    "30 days and collect his laptop.",
        impact=3, urgency=2, when=day(10, "15:10"),
        steps=[
            (50, "assign", "tom"),
            (2 * H, "start"),
            (2 * H + 5, "note", "assignee", "Scheduled for Fri 17:00: disable sign-in, revoke sessions, convert mailbox to shared "
                                            "(Liam full access), share OneDrive with Liam, remove licence after 30 days."),
            (2 * D + 2 * H, "resolve", "Mark Davis offboarded Friday 17:00: sign-in disabled, sessions revoked, mailbox converted to "
                                       "shared with Liam's access, auto-reply set, OneDrive shared with Liam, laptop collected."),
            (3 * D, "close"),
        ],
    ),
    Scenario(
        requester="sophia", asset="LT-0005",
        title="Screen sharing in Teams shows black screen",
        description="In Teams meetings, when I share my screen others just see a black screen. I'm on my MacBook.",
        impact=3, urgency=2, when=day(8, "13:55"),
        steps=[
            (20, "category", "Software"),
            (21, "assign", "tom"),
            (2 * H, "start"),
            (2 * H + 5, "reply", "assignee", "This is a macOS permission. Go to System Settings > Privacy & Security > Screen & System "
                                             "Audio Recording, switch on Microsoft Teams, then quit and reopen Teams. The KB article "
                                             "'Teams or Zoom meeting problems' has screenshots."),
            (2 * H + 40, "reply", "requester", "That worked!"),
            (2 * H + 45, "resolve", "Enabled the Screen Recording permission for Teams on macOS."),
            (D, "close"),
            (D + 1, "survey", 5, "I'd have found it myself if I'd checked the knowledge base first!"),
        ],
    ),
    Scenario(
        requester="mia", asset="LT-0003",
        title="OneDrive won't sync Finance folder",
        description="OneDrive shows a red X on the Finance shared folder and says some files can't sync.",
        impact=3, urgency=2, when=day(14, "11:45"),
        steps=[
            (H, "start"),
            (H + 10, "reply", "assignee", "Some files are nested so deep that the path is over the limit. Can I shorten the folder "
                                          "names with you now? It takes about 10 minutes."),
            (H + 15, "reply", "requester", "Yes, go ahead."),
            (2 * H, "resolve", "Sync errors caused by paths over 400 characters in Finance > Archive. Flattened two folder levels "
                               "with the user; all files synced."),
            (D, "close"),
        ],
    ),
    Scenario(
        requester="noah", asset="OT-0002",
        title="Barcode scanner types wrong characters",
        description="The barcode scanner beeps but the numbers come out wrong in the inventory app - letters and symbols instead of numbers.",
        impact=2, urgency=2, when=day(9, "07:55"),
        steps=[
            (45, "category", "Hardware"),
            (46, "assign", "sam"),
            (70, "start"),
            (80, "reply", "assignee", "The PC's keyboard layout had switched to French (Canada), so the scanner's input came out wrong "
                                      "(the scanner acts like a keyboard). I've removed the extra layout."),
            (85, "resolve", "Keyboard layout on the warehouse PC had switched to FR-CA. Removed the extra layout; scans correct."),
            (4 * H, "close"),
            (4 * H + 1, "survey", 5, ""),
        ],
    ),
    Scenario(
        requester="eric",
        title="How do I get the CRM on my phone?",
        description="Is there an app for the CRM? I want to check customer details when I'm on the road.",
        impact=3, urgency=3, when=day(11, "12:10"),
        steps=[(3 * H, "cancel", "requester", "Found the app in the App Store and signed in with my work account - all good.")],
    ),
    Scenario(
        requester="chloe",
        title="Accidentally deleted supplier contracts folder",
        description="I accidentally deleted the 'Supplier Contracts 2025' folder on the S: drive while tidying up. "
                    "We need it for an audit tomorrow morning.",
        impact=2, urgency=1, when=day(6, "16:40"),
        steps=[
            (15, "start"),
            (20, "reply", "assignee", "Don't worry - the file server keeps previous versions. Please don't save anything else into "
                                      "that area for now."),
            (45, "resolve", "Restored 'Supplier Contracts 2025' (214 files) from the file server's previous versions (12:00 snapshot). "
                            "User confirmed everything is there."),
            (60, "close"),
            (61, "survey", 5, "Lifesaver."),
        ],
    ),
    Scenario(
        requester="lucas", asset="LT-0004",
        title="VPN times out from hotel",
        description="I'm at a hotel in Ottawa and the VPN says 'connection timed out'. Hotel Wi-Fi works fine for websites.",
        impact=3, urgency=1, when=day(5, "19:30"),
        steps=[
            (13 * H, "start"),
            (13 * H + 5, "reply", "assignee", "Some hotel networks block VPN traffic. Could you try through your phone's hotspot - "
                                              "does the VPN connect then?"),
            (13 * H + 30, "reply", "requester", "Hotspot works. I'll use that for now."),
            (13 * H + 35, "resolve", "Hotel network blocks the VPN's UDP port. Workaround: phone hotspot. Enabled the SSL VPN fallback "
                                     "on TCP 443 so it works on restrictive networks in future."),
            (2 * D, "close"),
        ],
    ),
    Scenario(
        requester="emma", asset="LT-0001",
        title="Laptop very slow, fans always loud",
        description="My laptop has become very slow over the last few weeks. The fans are loud all the time and Outlook takes ages to open.",
        impact=3, urgency=3, when=day(4, "09:20"),
        steps=[
            (2 * H, "category", "Hardware"),
            (2 * H + 1, "assign", "sam"),
            (5 * H, "start"),
            (5 * H + 10, "reply", "assignee", "Your C: drive was 97% full, mostly an old Outlook data file and Downloads. I've freed about "
                                              "60 GB and it's noticeably quicker. The laptop is also 4 years old, so I've flagged it for "
                                              "replacement in the next budget round."),
            (5 * H + 15, "resolve", "Freed ~60 GB (old PST archive moved to OneDrive, Downloads and temp files cleared). "
                                    "Flagged LT-0001 for replacement in the asset register."),
            (2 * D, "close"),
            (2 * D + 1, "survey", 4, ""),
        ],
    ),
    Scenario(
        requester="lucas",
        title="Can't access the sales@ shared mailbox",
        description="I need to answer customer emails in the sales@ shared mailbox but it doesn't show up in my Outlook. Eric has it.",
        impact=3, urgency=2, when=day(13, "09:50"),
        steps=[
            (60, "category", "Account & Access"),
            (61, "assign", "tom"),
            (2 * H, "start"),
            (2 * H + 10, "note", "assignee", "Access request - approval from Eric (team lead) confirmed in Teams."),
            (2 * H + 30, "reply", "assignee", "You now have access and can send as sales@. Restart Outlook in about 30 minutes and it "
                                              "will appear in your folder list."),
            (2 * H + 31, "resolve", "Granted Full Access + Send As on the sales@ shared mailbox (approved by Eric Singh)."),
            (D, "close"),
        ],
    ),
    Scenario(
        requester="mia",
        title="People hear an echo in my Teams calls",
        description="Everyone hears an echo of themselves when I'm in Teams calls.",
        impact=3, urgency=2, when=day(3, "10:00"),
        steps=[
            (40, "category", "Software"),
            (41, "assign", "tom"),
            (3 * H, "start"),
            (3 * H + 5, "reply", "assignee", "It sounds like your laptop speakers are feeding back into the microphone. Could you try "
                                             "the USB headset I've left on your desk?"),
            (3 * H + 10, "resolve", "Echo caused by laptop speakers + built-in mic. Provided a USB headset."),
            (D + 2 * H, "close"),
            (D + 2 * H + 1, "survey", 2, "The headset helps, but I still hear an echo sometimes when others are on speakers."),
        ],
    ),
    # ------------------------------------------------------------------ live queue
    Scenario(
        requester="eric", asset="LT-0002",
        title="VPN disconnecting every hour",
        description="Working from home, the VPN connection keeps dropping. Internet itself is fine.",
        impact=2, urgency=1, when=ago(5 * H),
        steps=[
            (20, "start"),
            (25, "reply", "assignee", "Does it drop at a regular interval? Could you note the times it disconnects today?"),
            (2 * H, "reply", "requester", "10:02, 11:02 and 12:03 - almost exactly every hour."),
            (2 * H + 20, "note", "assignee", "Hourly drops point to a re-key timer mismatch. Checking the firewall's IPsec phase 2 "
                                             "lifetime against the client profile."),
            (4 * H, "reply", "assignee", "Thanks, that pattern really helps. I found a timer mismatch on the firewall and changed it. "
                                         "Could you let me know if it drops again in the next couple of hours?"),
        ],
    ),
    Scenario(
        requester="emma", asset="LT-0001",
        title="Laptop screen flickering with dock",
        description="My laptop screen flickers when I plug in the dock. Fine without the dock.",
        impact=3, urgency=2, when=ago(26 * H),
        steps=[
            (3 * H, "start"),
            (3 * H + 10, "reply", "assignee", "Could you try the other USB-C port (the one with the lightning symbol) and tell me if the "
                                              "flicker continues?"),
            (20 * H, "reply", "requester", "Still flickers on both ports, only when the dock is connected."),
            (21 * H, "note", "assignee", "Dock firmware is outdated. Firmware + graphics driver update booked with the user for tomorrow 8am."),
        ],
    ),
    Scenario(
        requester="ava",
        title="Computer acting strange",
        description="My computer keeps doing weird things - windows opening by themselves and it is really slow. Can someone call me? Ext 201.",
        impact=3, urgency=3, when=ago(40),
    ),
    Scenario(
        requester="daniel", channel="phone", asset="OT-0001",
        title="Boardroom TV won't show my laptop",
        description="The boardroom TV won't display my laptop. I have a client meeting in there in an hour.",
        impact=2, urgency=1, when=ago(75),
        steps=[
            (5, "category", "Hardware"),
            (6, "assign", "sam"),
            (10, "start"),
            (12, "reply", "assignee", "On my way to the boardroom now."),
            (35, "note", "assignee", "HDMI cable damaged at the connector. Using a spare USB-C to HDMI adapter; new cable ordered."),
            (40, "reply", "assignee", "You're connected with an adapter for today's meeting. I'll replace the damaged cable this week "
                                      "and close the ticket then."),
        ],
    ),
    Scenario(
        requester="mia", asset="LT-0003",
        title="Payroll portal shows 'Your connection is not private'",
        description="When I open the payroll provider's website, Chrome shows 'Your connection is not private' "
                    "(NET::ERR_CERT_DATE_INVALID). Payroll must be submitted by 4pm tomorrow.",
        impact=2, urgency=1, when=ago(6 * H + 30),
        steps=[
            (25, "category", "Software"),
            (26, "assign", "tom"),
            (50, "start"),
            (55, "reply", "assignee", "Please don't click through the warning. Is the date and time on your laptop correct?"),
            (90, "reply", "requester", "Yes, the clock is right. Emma gets the same error."),
            (2 * H, "note", "assignee", "Other HTTPS sites fine; only the payroll portal fails. Vendor's certificate expired. "
                                        "Called vendor support - they're renewing it."),
            (3 * H, "reply", "assignee", "The payroll company confirmed their website certificate expired and they're renewing it. "
                                         "I'll update you as soon as it's fixed - there's still time before tomorrow's deadline."),
        ],
    ),
    Scenario(
        requester="chloe", asset="PR-0001",
        title="2nd floor printer jams on every job",
        description="The 2nd floor printer jams on almost every print job. We've cleared it several times today.",
        impact=3, urgency=2, when=ago(2 * D),
        steps=[
            (60, "category", "Hardware"),
            (61, "assign", "sam"),
            (3 * H, "start"),
            (3 * H + 10, "reply", "assignee", "I've cleared the jam and cleaned the rollers. It's printing again, but the fuser shows "
                                              "wear so I've ordered a maintenance kit."),
            (3 * H + 15, "hold", "Waiting for the fuser maintenance kit (ETA 3-5 business days). Printer usable meanwhile."),
        ],
    ),
    Scenario(
        requester="olivia",
        title="New phone - Authenticator doesn't have my work account",
        description="I got a new phone and the Authenticator app doesn't have my work account. "
                    "I can't sign in to email on my laptop now.",
        impact=3, urgency=1, when=ago(30),
        steps=[(5, "reply", "requester", "I still have my old phone at home if that helps.")],
    ),
    Scenario(
        requester="liam", asset="LT-0007",
        title="S: shared drive missing after Windows update",
        description="Since the Windows update last night the S: drive is missing on my laptop and on Chloe's. "
                    "We can still reach the files by typing \\\\fileserver\\shared.",
        impact=2, urgency=2, when=ago(22 * H),
        steps=[
            (30, "category", "Files & Storage"),
            (31, "assign", "tom"),
            (40, "start"),
            (50, "reply", "assignee", "Thanks - typing the full path is the right workaround for now. I'm checking the drive-mapping policy."),
            (3 * H, "note", "assignee", "Last night's update broke the legacy logon-script drive mapping. Moving S: to a Group Policy "
                                        "drive map; testing on Liam's laptop."),
            (20 * H, "reply", "assignee", "The new drive mapping is in place. Please restart your laptop and check that S: is back."),
        ],
    ),
    Scenario(
        requester="sophia", asset="LT-0005",
        title="Request: second monitor for design work",
        description="Could I get a second 27\" monitor? I'm constantly switching windows when laying out print materials.",
        impact=3, urgency=3, when=ago(2 * D),
        steps=[
            (3 * H, "category", "Hardware"),
            (3 * H + 1, "assign", "tina"),
            (6 * H, "start"),
            (6 * H + 10, "reply", "assignee", "We don't have a 27\" monitor in stock, so I've asked Daniel to approve the purchase."),
            (6 * H + 15, "hold", "Waiting for purchase approval for a second 27\" monitor."),
        ],
    ),
    Scenario(
        requester="chloe", asset="LT-0008",
        title="Clicked a phishing link and entered my password",
        description="I clicked a DocuSign link in an email about a supplier contract and typed my email password on the page. "
                    "Then I noticed the sender address was strange.",
        impact=2, urgency=1, when=ago(25),
        steps=[
            (3, "category", "Security"),
            (4, "assign", "tina"),
            (5, "start"),
            (7, "reply", "assignee", "Thanks for reporting it straight away - that makes a big difference. I've reset your password and "
                                     "signed you out everywhere. I'll call you in 2 minutes to set a new one."),
            (12, "note", "assignee", "Sessions revoked, password reset, MFA methods reviewed (no new method added). Sign-in logs: one "
                                     "attempt from an overseas IP 3 min after the click, blocked by MFA. Now checking inbox rules and "
                                     "whether the email reached other mailboxes."),
        ],
    ),
    Scenario(
        requester="lucas", asset="LT-0004",
        title="Outlook keeps asking for my password",
        description="Since I changed my password yesterday, Outlook pops up a password box every few minutes. "
                    "I type it in and it comes back.",
        impact=3, urgency=2, when=ago(3 * H),
        steps=[(30, "category", "Email"), (31, "assign", "tom")],
    ),
    Scenario(
        requester="eric", asset="LT-0002",
        title="Mailbox full - can't send quotes to customers",
        description="Outlook says my mailbox is full and I can't send. I have quotes to send to customers today.",
        impact=3, urgency=1, when=ago(27 * H),
        steps=[
            (5 * H, "start"),
            (5 * H + 5, "reply", "assignee", "Your mailbox is almost at its limit. As a quick fix, please empty Deleted Items - that frees "
                                             "several GB. I'm also turning on the online archive so older mail moves out automatically."),
            (6 * H, "reply", "requester", "Emptied Deleted Items, I can send again."),
            (7 * H, "note", "assignee", "Online archive enabled + retention policy (move to archive after 2 years). "
                                        "Initial archive processing can take 24h+; keep open to confirm."),
        ],
    ),
    Scenario(
        requester="ava", asset="PR-0002",
        title="Front desk printer printing blank pages",
        description="The front desk printer feeds paper but the pages come out completely blank. We just put in a new toner.",
        impact=3, urgency=2, when=ago(20 * H),
        steps=[
            (30, "category", "Hardware"),
            (31, "assign", "sam"),
            (2 * H, "start"),
            (2 * H + 20, "resolve", "The new toner cartridge still had its protective seal on. Removed it and printed test pages "
                                    "successfully. (KB: 'Print quality problems and paper jams')"),
        ],
    ),
    Scenario(
        requester="emma",
        title="Request: Adobe Acrobat Pro to edit PDFs",
        description="I need to edit and combine PDF invoices from suppliers. Could I get Adobe Acrobat Pro?",
        impact=3, urgency=3, when=ago(50),
    ),
    Scenario(
        requester="noah", asset="LT-0010",
        title="Laptop case bulging near touchpad",
        description="The bottom of my laptop is bulging and the touchpad is lifting up. It gets hot when charging.",
        impact=3, urgency=1, when=ago(90),
        steps=[
            (10, "category", "Hardware"),
            (11, "assign", "sam"),
            (15, "start"),
            (16, "reply", "assignee", "Please stop using it and unplug it now - this sounds like a swollen battery, which can be a fire "
                                      "risk. Leave it on the desk away from anything flammable. I'll collect it and bring you a loaner "
                                      "within 30 minutes."),
            (40, "note", "assignee", "Collected LT-0010 - battery visibly swollen, stored in a fire-safe bag. Loaner LT-0011 issued. "
                                     "Warranty expired; laptop is 5 years old - recommending replacement over battery repair."),
        ],
    ),
    Scenario(
        requester="daniel",
        title="Website contact form emails not arriving",
        description="Customers say they filled in the contact form on our website but nobody received the emails. "
                    "The last one we got was on Monday.",
        impact=2, urgency=2, when=ago(3 * D),
        steps=[
            (2 * H, "category", "Email"),
            (2 * H + 1, "assign", "tom"),
            (3 * H + 30, "start"),
            (3 * H + 40, "reply", "assignee", "The website sends its emails through a mail account whose password expired. I've contacted "
                                              "the web agency that hosts the site to update it."),
            (3 * H + 45, "hold", "Waiting for the web agency to update the website's email settings."),
        ],
    ),
]
