# Converts a total number of seconds into a 12:34 or 1:23:45 timestamp
# If the total length of the video is under an hour, it goes with the short one
def display_timestamp(seconds: int, total_seconds: int) -> str:
    h = seconds // 3600
    m = (seconds - h*3600) // 60
    s = seconds - h*3600 - m*60
    if total_seconds >= 3600: 
        return f"{h:01d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


# Attaches a 12s or 12m34s or 1h23m45s timestamp to a url
def timestamp_url(url: str, seconds: int) -> str:
    if not url:
        return ""

    h = seconds // 3600
    m = (seconds - h*3600) // 60
    s = seconds - h*3600 - m*60

    # Decide whether to attach a ?t= or a &t=
    if "?" in url:
        query_string = "&t="
    else:
        query_string = "?t="

    # Decide on what format to use depending on length
    if h > 0: 
        return f"{url}{query_string}{h}h{m}m{s}s"
    elif m > 0: 
        return f"{url}{query_string}{m}m{s}s"
    elif s > 0:
        return f"{url}{query_string}{s}s"
    else:
        return url