import cgi


def get_content_type(response):
    header = response.headers.get('content-type')
    if not header:
        return None

    return cgi.parse_header(header)[0]
