def get_content_type(response):
    header = response.headers.get('content-type')
    if not header:
        return None

    bits = header.split(';', 1)
    return bits[0].strip()
