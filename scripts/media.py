"""Media evidence, deliberately separate from scientific/manual validity."""
from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import re
import socket
from urllib.parse import unquote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

if __package__:
    from .github_api import atomic_json
else:
    from github_api import atomic_json

URL_PATTERN = re.compile(r'https?://[^\s<>"\']+', re.I)
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.mkv', '.m4v', '.avi', '.ogv'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.avif'}
DOCUMENT_EXTENSIONS = {'.txt', '.log', '.json', '.zip', '.gz', '.tar', '.7z', '.pdf', '.md', '.patch', '.diff', '.csv', '.xml', '.yaml', '.yml', '.exe', '.dmg'}


def clean_url(url):
    url = url.rstrip('.,;!?:')
    for closing, opening in ((')', '('), (']', '['), ('}', '{')):
        while url.endswith(closing) and url.count(closing) > url.count(opening):
            url = url[:-1]
    return url


def markdown_links(text):
    """Yield inline link spans and destinations, keeping URL labels out of bare links."""
    for match in re.finditer(r'(!?)\[([^\]\n]*)\]\(\s*', text):
        start = match.end()
        position, depth = start, 0
        angled = text[start:start + 1] == '<'
        if angled:
            end = text.find('>', start + 1)
            if end < 0:
                continue
            destination = text[start + 1:end]
            position = end + 1
        else:
            while position < len(text):
                char = text[position]
                if char == '\\' and position + 1 < len(text):
                    position += 2
                    continue
                if char == '(':
                    depth += 1
                elif char == ')':
                    if depth == 0:
                        break
                    depth -= 1
                elif char.isspace() and depth == 0:
                    break
                position += 1
            destination = text[start:position]
        # Optional quoted titles belong to the link, not its URL.
        suffix = re.match(r'\s*(?:"[^"\n]*"|\'[^\'\n]*\'|\([^\n)]*\))?\s*\)', text[position:])
        if suffix:
            destination = re.sub(r'\\([\\()])', r'\1', destination)
            yield match.start(), position + suffix.end(), destination, match.group(2), bool(match.group(1))


def classify_video_url(url):
    try:
        parsed = urlparse(url)
        host, path = (parsed.hostname or '').lower(), unquote(parsed.path).lower()
    except ValueError:
        return None
    if parsed.scheme not in ('http', 'https'):
        return None
    if host == 'github.com' and (path.startswith(('/user-attachments/assets/', '/user-attachments/files/')) or re.match(r'^/[^/]+/[^/]+/(?:assets|files)/', path)):
        return 'github_attachment'
    if host == 'user-images.githubusercontent.com':
        return 'github_attachment'
    if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com') and (path == '/watch' and 'v=' in parsed.query or path.startswith(('/embed/', '/shorts/', '/live/'))):
        return 'youtube'
    if host in ('youtu.be', 'www.youtu.be') and path.strip('/'):
        return 'youtube'
    if host in ('streamable.com', 'www.streamable.com') and path.strip('/'):
        return 'streamable'
    if host in ('vimeo.com', 'www.vimeo.com', 'player.vimeo.com') and re.search(r'/\d+', path):
        return 'vimeo'
    if any(path.endswith(ext) for ext in VIDEO_EXTENSIONS):
        return 'video_file'
    return None


def detect_media(body, probe=None):
    text = html.unescape(body or '')
    found = {}
    links = list(markdown_links(text))
    bare_text = list(text)
    references = []
    for start, end, destination, label, is_image in links:
        bare_text[start:end] = ' ' * (end - start)
        if re.match(r'https?://', destination, re.I):
            references.append((start, destination, label, is_image))
    references.extend((match.start(), clean_url(match.group()), '', False)
                      for match in URL_PATTERN.finditer(''.join(bare_text)))
    for position, url, label_text, markdown_image in sorted(references):
        try:
            parsed = urlparse(url)
            if not parsed.hostname:
                continue
        except ValueError:
            continue
        path = unquote(parsed.path).lower()
        kind = classify_video_url(url)
        image = any(path.endswith(ext) for ext in IMAGE_EXTENSIONS)
        document = any(path.endswith(ext) for ext in DOCUMENT_EXTENSIONS)
        # The label adjacent to this URL belongs to this attachment, unlike nearby prose.
        prefix = text[max(0, position-300):position]
        image_markup = markdown_image or bool(re.search(r'<img\b[^>]*$', prefix, re.I))
        video_markup = bool(re.search(r'<(?:video|source)\b[^>]*$', prefix, re.I))
        # A URL used as display text is not filename evidence about its destination.
        label_text = '' if URL_PATTERN.search(label_text) else label_text.lower()
        filename_video = any(re.search(re.escape(ext) + r'(?:\b|$)', label_text) for ext in VIDEO_EXTENSIONS)
        filename_image = any(label_text.endswith(ext) for ext in IMAGE_EXTENSIONS)
        filename_document = any(label_text.endswith(ext) for ext in DOCUMENT_EXTENSIONS)
        if not (kind or image or image_markup or video_markup or filename_video or filename_image):
            continue
        if document or filename_document:
            status, evidence = 'non_video', ['document/archive/log filename']
        elif image or image_markup or filename_image:
            status, evidence = 'non_video', ['image extension/markup']
        elif kind in ('youtube', 'vimeo', 'streamable'):
            status, evidence = 'video', ['video hosting URL (content unverified)']
        elif any(path.endswith(ext) for ext in VIDEO_EXTENSIONS) or filename_video:
            status, evidence = 'video', ['video filename extension']
        elif video_markup:
            status, evidence = 'possible_video', ['HTML video/source element']
        else:
            status, evidence = 'possible_video', ['opaque GitHub attachment; type unknown']
        if probe and (kind == 'github_attachment' or video_markup):
            try:
                metadata = probe(url)
                mime = metadata.get('content_type', '').split(';')[0].strip().lower()
                disposition = metadata.get('content_disposition', '').lower()
                if mime.startswith('video/'):
                    status = 'video'
                    evidence.append('HTTP Content-Type: ' + mime)
                elif mime.startswith(('image/', 'text/')) or mime in ('application/pdf', 'application/zip'):
                    status = 'non_video'
                    evidence.append('HTTP Content-Type: ' + mime)
                elif any(re.search(re.escape(ext) + r'(?:[\";\s]|$)', disposition) for ext in VIDEO_EXTENSIONS):
                    status = 'video'
                    evidence.append('HTTP video filename')
                elif any(re.search(re.escape(ext) + r'(?:[\";\s]|$)', disposition) for ext in IMAGE_EXTENSIONS):
                    status = 'non_video'
                    evidence.append('HTTP image filename')
                elif metadata.get('error'):
                    evidence.append(metadata['error'])
            except (OSError, ValueError) as error:
                evidence.append('metadata unavailable: ' + type(error).__name__)
        item = {'url': url, 'video_type': kind or ('image' if image or image_markup else 'html_video'),
                'media_status': status, 'evidence': '; '.join(evidence)}
        # A later image-only reference must not erase stronger video metadata evidence.
        if url not in found or (found[url]['media_status'] != 'video' and status == 'video'):
            found[url] = item
    return list(found.values())


def _public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('non-public media URL')
    if parsed.port not in (None, 80, 443):
        raise ValueError('nonstandard media port')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('private/reserved media address')


class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _public_url(newurl)
        # urllib normally changes redirected HEAD to GET; avoid downloading recordings.
        return Request(newurl, headers={'User-Agent': 'game-bug-video-retrieval/0.2'}, method='HEAD')


class MediaProbe:
    """Unauthenticated HEAD only, with a persistent cache. Never forwards a GitHub token."""
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.failures = {}

    def __call__(self, url):
        if url in self.failures:
            return self.failures[url]
        path = self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.json')
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        try:
            _public_url(url)
            request = Request(url, headers={'User-Agent': 'game-bug-video-retrieval/0.2'}, method='HEAD')
            with build_opener(PublicRedirects()).open(request, timeout=10) as response:
                result = {'content_type': response.headers.get('Content-Type', ''),
                          'content_disposition': response.headers.get('Content-Disposition', '')}
        except (OSError, ValueError) as error:
            # Don't cache failures permanently: a later resume may have network access.
            result = {'error': 'metadata unavailable: ' + type(error).__name__}
            self.failures[url] = result
            return result
        atomic_json(path, result)
        return result
