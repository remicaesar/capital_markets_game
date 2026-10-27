"""
Fictional startup names, sectors and pitch fragments for venture fund mode

Names are assembled from made-up syllables; none is meant to be a real company.
"""

NAME_ROOTS = [
    "Quor", "Lumet", "Brindl", "Tavor", "Ostr", "Velm", "Kesta", "Mirav", "Solv",
    "Pellu", "Ruvo", "Calv", "Drayn", "Fenra", "Ivol", "Zentr", "Halc", "Obri",
    "Nimb", "Arvel", "Corv", "Plinth", "Tessel", "Yarro", "Wexl", "Glimm",
]
NAME_SUFFIXES = ["ly", "io", "ara", "ix", "ora", "wick", "loop", "stack", "grid",
                 "works", "base", "nest", "lane", "forge"]

# sector -> (products, customers, traction lines)
SECTORS = {
    "Fintech": (
        ["payroll rails", "embedded lending", "treasury automation", "fraud scoring",
         "cross-border invoicing"],
        ["gig platforms", "freight brokers", "dental clinics", "SMB exporters",
         "independent pharmacies"],
    ),
    "Climate": (
        ["heat-pump installation software", "grid battery scheduling",
         "carbon accounting", "industrial heat recovery", "EV fleet charging"],
        ["utilities", "mid-size factories", "property managers", "school districts",
         "delivery fleets"],
    ),
    "Health": (
        ["prior-authorisation automation", "remote cardiac monitoring",
         "clinical trial matching", "nurse scheduling", "at-home lab testing"],
        ["rural hospitals", "specialty clinics", "employers", "insurers",
         "home-care agencies"],
    ),
    "Dev Tools": (
        ["flaky-test detection", "database branching", "API contract testing",
         "cloud cost guardrails", "on-call triage"],
        ["platform teams", "mobile studios", "data engineers", "fintech backends",
         "open-source maintainers"],
    ),
    "AI": (
        ["document extraction agents", "voice support agents", "model evaluation",
         "contract review copilots", "inventory forecasting models"],
        ["insurers", "law firms", "call centres", "retail chains", "logistics firms"],
    ),
    "Consumer": (
        ["language-learning games", "secondhand furniture resale", "pet telehealth",
         "group travel planning", "home repair booking"],
        ["Gen Z renters", "new parents", "retirees", "college students",
         "urban commuters"],
    ),
}

# Traction lines per entry stage; {growth} is filled in from the startup's own rng
TRACTION = {
    "Seed": ["{mrr}k MRR, growing {growth}% a month",
             "{pilots} paying pilots, two converting to annual contracts",
             "waitlist of {waitlist}k, launching next quarter"],
    "Series A": ["${arr}M ARR, {growth}% month-on-month for a year",
                 "{customers} customers, net revenue retention {nrr}%"],
    "Series B": ["${arr}M ARR, tripled last year", "{customers} enterprise customers, "
                 "net revenue retention {nrr}%"],
}
