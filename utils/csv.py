from datetime import date
from re import fullmatch
import logging

# list of regions (Following the same naming as TWB)
region_list = [
    "Europe", 
    "Asia", 
    "North America", 
    "Oceania", 
    "South America"
]

# list of Skullgirls versions (Following the same naming as TWB)
# https://github.com/Servan42/TWB_Parser/blob/master/List_of_CharactersCode_Regions_Versions.md
version_list = [
    '2024 Balance Patch',
    'Marie Patch',
    'Marie Alpha',
    'Black Dahlia Patch',
    'Black Dahlia Alpha',
    'Umbrella Patch',
    # I didn't bother to mark any Umbrella Patch Beta vods as such
    'Annie Patch',
    'Annie Patch Beta',
    '2E+ Final',
    '2E+ (old UD)',
    '2E', # aka. Robo-Fortune Patch
    'Beowulf Patch',
    'Eliza Patch',
    'Fukua Patch',
    'Big Band Patch',
    'Encore',
    'MDE',
    'SDE'
    # Note: there are no "Vanilla" vods on TWB, SDE is the earliest
]

# Issue warnings for missing or invalid twb csv parameters
def validate_csv_fields(event, date, region, netplay, version, url):    
    # Issue some warnings if not all the csv fields are supplied 
    # (the csv will have some missing fields in it, but some users won't care) 
    missing_fields = []
    if not event:
        missing_fields.append("EVENT")
    if not date:
        missing_fields.append("DATE")
    if not region:
        missing_fields.append("REGION")
    if netplay is None:
        missing_fields.append("NETPLAY")
    if not version:
        missing_fields.append("VERSION")
    if not url:
        missing_fields.append("URL")
    if missing_fields:
        logging.warning(
            "The following value(s) were not supplied: "
            f"""{', '.join(missing_fields)}. The resulting csv file will """
            "have missing fields.\nIf you only care about generating "
            "timestamps, then you can ignore this warning or use --no-csv to "
            "suppress it in future."
        )

    # Warn if date isn't in the right format (YYYY-MM-DD or DD/MM/YYYY)
    iso_date_format = r"\d{4}-\d{2}-\d{2}"
    slashy_date_format = r"\d{2}/\d{2}/\d{4}"
    if date and not (fullmatch(iso_date_format, date) or fullmatch(slashy_date_format, date)):
        logging.warning("Date in incorrect format for TWB, use YYYY-MM-DD or DD/MM/YYYY.")

    # Warn if region not one of the listed regions
    if region not in region_list:
        logging.warning(f"""Region not one of [{', '.join(region_list)}]""")

    # Warn if netplay not a binary flag
    if netplay != 0 and netplay != 1:
        logging.warning(f"Netplay flag not one of [0, 1]")

    # Warn if region not one of the listed regions
    if version not in version_list:
        logging.warning(f"""Version not one of [{', '.join(version_list)}]""")


# TWB csv header
def twb_csv_header():
    return "Event,Date,Region,Netplay,Version," \
           "P1Name,P1Char1,P1Char2,P1Char3," \
           "P2Name,P2Char1,P2Char2,P2Char3,URL"


# TWB csv row representation of a vod timestamp
def twb_csv_row(
    event, date, region, netplay, version,
    p1name, p1char1, p1char2, p1char3,
    p2name, p2char1, p2char2, p2char3,
    url
):
    # Encapsulate any comma-containing fields in ""
    event   = (f"\"{event}\""  if "," in event  else event)
    p1name  = (f"\"{p1name}\"" if "," in p1name else p1name)
    p2name  = (f"\"{p2name}\"" if "," in p2name else p2name)
    return f"{event},{date},{region},{netplay},{version}," \
           f"{p1name},{p1char1},{p1char2},{p1char3}," \
           f"{p2name},{p2char1},{p2char2},{p2char3},{url}"