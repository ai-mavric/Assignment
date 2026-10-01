import re

US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'DC': 'District of Columbia',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois',
    'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
    'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon',
    'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota',
    'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia',
    'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
}
STATE_NAME_TO_CODE = {name.lower(): code for code, name in US_STATES.items()}

_LSAD_SUFFIX = re.compile(
    r'\s+(?:zona urbana|comunidad|cdp|city|town|village|borough|municipality|township|ccd|'
    r'plantation|corporation|county|(?:metro|metropolitan|unified|consolidated|urban county)\s+government)$'
)
_ABBREVIATIONS = {'saint': 'st', 'sainte': 'ste', 'fort': 'ft', 'mount': 'mt', 'mountain': 'mtn'}


def normalize_place_name(name: str, strip_lsad: bool = False) -> str:
    s = name.lower().strip()
    s = re.sub(r'\(.*?\)', ' ', s).strip()
    if strip_lsad:
        s = _LSAD_SUFFIX.sub('', s)
    s = re.sub(r'[^a-z0-9 ]+', ' ', s.replace("'", ''))
    return ' '.join(_ABBREVIATIONS.get(w, w) for w in s.split())


def normalize_state(value: str) -> str | None:
    v = value.strip()
    if v.upper() in US_STATES:
        return v.upper()
    return STATE_NAME_TO_CODE.get(v.lower())
