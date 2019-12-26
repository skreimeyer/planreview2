"""Generates comment letters in PDF format."""

import os
from datetime import date
from typing import List, Dict
from fpdf import FPDF

HT = 5
WD = 165
MODPATH = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(MODPATH,'resources','pw_logo.png')
SIG = os.path.join(MODPATH,'resources','signature.png')

class PDF(FPDF):
    def letterhead(self):
        self.image(LOGO,15,12.5,25)
        self.set_font("times", "B", size=14)
        self.cell(37.5)
        self.cell(0, 12.5, txt="City of Little Rock", ln=1)
        self.line(50, 18.75, 175, 18.75)
        self.set_font("times", "B", size=9)
        self.cell(37.5)
        self.cell(50, 0, txt="Public Works")
        self.set_font("times", size=9)
        self.cell(75, 0, txt="701 W Markham", align="R", ln=1)
        self.cell(37.5)
        self.cell(50, 6, txt="Civil Engineering")
        self.cell(75, 6, txt="Little Rock, Arkansas 72201", align="R", ln=1)
        self.cell(37.5)
        self.cell(50, 6)
        self.cell(75, 0, txt="phone: (501) 371-4811", align="R", ln=1)
        self.cell(37.5)
        self.cell(50, 6)
        self.cell(75, 6, txt="www.littlerock.gov", align="R", ln=1)
   
    def sign(self):
        signature = """Samuel Kreimeyer
Civil Engineer I, CFM
City of Little Rock Public Works
701 W Markham Street
Little Rock, AR 72201
(501) 918-5348
"""
        self.cell(0,HT,"Sincerely,",ln=1)
        self.image(SIG,w=40)
        self.multi_cell(w=0,h=HT,txt=signature)

def today() -> str:
    return date.today().strftime("%B %d, %Y")

def generate(comments: List[str], app: Dict[str,str], project: str, approved:bool) -> FPDF:
    heading =f"""{date.today().strftime("%B %d, %Y")} via email

{app['name']}
{app['title']}
{app['company']}
{app['address']}
{app['city_state_zip']}

Re: {project.title()}

Dear {app['salutation']},
"""
    opening_remarks = f"The above referenced plans are {'not ' if not approved else ''}approved with the following comments and conditions:"
    end_remarks = "If you have any questions or desire additional information, place contact me by phone at (501) 918-5348 or by email at skreimeyer@littlerock.gov"
    letter = PDF("P","mm","Letter")
    letter.add_page()
    letter.set_font('Arial','',12)
    letter.letterhead()
    letter.set_left_margin(25)
    letter.set_right_margin(25)
    letter.set_x(25)
    letter.set_y(50)
    letter.multi_cell(WD,HT, heading)
    letter.ln()
    letter.multi_cell(WD,HT, opening_remarks)
    for i,item in enumerate(comments):
        letter.set_x(30)
        letter.cell(10,HT,f"{i+1}.")
        letter.set_x(40)
        letter.multi_cell(135,HT,item)
    if letter.get_y() > 220:
        letter.ln(h=270 - letter.get_y())
    letter.multi_cell(WD,HT, end_remarks)
    letter.ln()
    letter.sign()
    return letter

def save(letter: FPDF, destination: str) -> ():
    letter.output(destination,'F')

