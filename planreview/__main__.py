import asyncio
import logging
import sys
import os

from planreview import esri
from planreview import comment

async def main() -> ():
    location = sys.argv[1]
    if ' ' in location: # it's an address
        loc = esri.geocode(location)
        if loc is None:
            logging.critical(f"Cannot geocode {location}! Exiting...")
            return
        params = esri.params_from_loc(loc)
    else:
        params = esri.params_from_pid(location)
    parcel = esri.fetch_parcel(params)
    ring = parcel.ring
    buffer_ring = esri.buffer_ring(ring, 100)
    floodhaz = await asyncio.coroutine(esri.floodmap)(ring)
    zoning = await asyncio.coroutine(esri.zoning)(ring)
    streets = await asyncio.coroutine(esri.trans)(buffer_ring)
    project = input("Project name: ")
    applicant = comment.Applicant(
        input("applicant name: "),
        input("applicant title: "),
        input("applicant salutation: "),
        input("applicant company: "),
        input("applicant address first line: "),
        input("applicant city, state zip: "),
    )
    subdivision = parse_yn('subdivision')
    grading = parse_yn('grading permit required')
    franchise = parse_yn('franchise required')
    wall = parse_yn('retaining wall')
    detention = parse_yn('detention required')
    approved = parse_yn('approved')
    meta = comment.Meta(subdivision, grading, franchise, wall, detention)
    master = comment.Master(meta,parcel,streets,floodhaz,zoning)
    base_comments = comment.generate_base_comments(master)
    more_comments = parse_yn("Make special comments")
    while more_comments:
        base_comments.append(input(">> "))
        more_comments = parse_yn("additional comments")
    comment.generate_letter(base_comments,applicant,project,"Public Works comments.pdf",approved)

def parse_yn(prompt: str):
    response = input(f"{prompt} (y/n): ")
    if response.strip().lower() == 'y':
        return True
    return False

if __name__ == "__main__":
    asyncio.run(main())