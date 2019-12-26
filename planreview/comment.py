"""## comment

comment uses information from the esri module to generate the complete text for
a Public Works comment letter for a response to a building permit or grading 
permit application.

Workflow for the comment module is expected to follow this basic pattern:
```
Query GIS -> Template base comments -> Add special comments -> final rendering
```

Review comments may be delivered via three different media:

- Planning Department web application
- email body
- formal letter

By convention, comments area always given as an ordered list of terse directives
with only a few additional sentences of context at most. For the sake of the 
CLR Planning Department, only that ordered list is necessary. For an email, some
typical style conventions, such as salutation and a closing statement are
expected.

Formal letter creation will require the generation of a PDF file, by convention,
which then means type-setting and insertion of letter-head and a signature are
expected. This is offloaded to its own module for clarity, but this module
will provide the necessary content in a digestible format.
"""

from jinja2 import Environment, PackageLoader
from dataclasses import dataclass
from typing import List, Set, Dict, Optional
import logging

from . import esri
from . import pdf

log = logging.getLogger(__name__)

@dataclass
class Applicant:
    name: str
    title: str
    salutation: str
    company: str
    address: str
    city_state_zip: str

@dataclass
class Meta:
    subdivision: bool = False
    grading: bool = True
    franchise: bool = False
    wall: bool = False
    detention: bool = True

@dataclass
class Master:
    meta: Meta
    parcel: esri.ParcelData
    streets: List[esri.Street]
    flood: Set[str]
    zone: esri.Zone

# FILTERS #
def permit_fee(acres: float) -> str:
    fee = min(60.0 * acres + 60.0,660.0)
    if acres <= 0.5:
        fee = 60.0
    if acres <= 1.0:
        fee = 120.0
    return f"{fee:.2f}"

def has_highway(streets: List[esri.Street]) -> bool:
    return True in [s.state for s in streets]
# END FILTERS #

env = Environment(loader=PackageLoader('planreview','templates'), autoescape=True)
env.filters['fee'] = permit_fee
env.filters['has_highway'] = has_highway

def generate_base_comments(master: Master) -> List[str]:
    template = env.get_template("base.tmpl")
    base = template.render(master=master)
    log.debug(base)
    return base.split('\n\n')

def generate_ips_comments(comments: List[str]) -> str:
    return '\r\n'.join((f"{i+1}. {c}" for i,c in enumerate(comments)))

def generate_email(comments: List[str], app: Applicant, approved: bool=False) -> str:
    template = env.get_template("email.tmpl")
    email_body = template.render(
        comments=comments,
        applicant=app,
        approved=approved
    )
    log.debug(email_body)
    return email_body

def generate_letter(comments: List[str],app: Applicant, project: str, dest: str="comment letter.pdf", approved: bool=False) -> ():
    app = app.__dict__ # This is a kludge to avoid shadowing
    letter = pdf.generate(comments, app, project, approved)
    pdf.save(letter,dest)

