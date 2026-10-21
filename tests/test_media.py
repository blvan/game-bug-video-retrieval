import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.media import classify_video_url, detect_media, MediaProbe, PublicRedirects, _public_url
from urllib.request import Request


class MediaTests(unittest.TestCase):
    def test_extended_formats_and_hosts(self):
        links = ['https://example.org/a.mkv?download=1', 'https://example.org/a.WEBM',
                 'https://streamable.com/abc', 'https://player.vimeo.com/video/123',
                 'https://youtube.com/shorts/xyz', 'https://youtu.be/abc']
        self.assertTrue(all(classify_video_url(url) for url in links))
        self.assertTrue(all(row['media_status'] == 'video' for row in detect_media(' '.join(links))))
        for url in ['https://youtube.com/', 'https://youtube.com/@channel', 'https://streamable.com.evil.com/abc',
                    'https://vimeo.com/', 'https://example.org/a.mp4.exe', 'https://[broken/']:
            self.assertIsNone(classify_video_url(url))

    def test_opaque_attachment_is_uncertain_not_confirmed_video(self):
        row, = detect_media('https://github.com/user-attachments/assets/opaque')
        self.assertEqual(row['media_status'], 'possible_video')

    def test_mime_differentiates_video_and_image(self):
        url = 'https://github.com/user-attachments/assets/opaque'
        video, = detect_media(url, lambda _: {'content_type': 'video/mp4'})
        image, = detect_media(url, lambda _: {'content_type': 'image/png'})
        self.assertEqual(video['media_status'], 'video')
        self.assertEqual(image['media_status'], 'non_video')

    def test_markdown_filename_html_and_legacy_images(self):
        text = ('[repro.mkv](https://github.com/owner/game/assets/id) '
                '![Screenshot](https://github.com/user-attachments/assets/picture) '
                '<video src="https://example.org/download?id=1"></video> '
                'https://user-images.githubusercontent.com/1/demo.mp4 '
                '<img src="https://example.org/pic">')
        rows = detect_media(text)
        self.assertEqual([r['media_status'] for r in rows], ['video', 'non_video', 'possible_video', 'video', 'non_video'])
        self.assertEqual(rows[0]['video_type'], 'github_attachment')

    def test_image_mime_overrides_filename_and_probe_failure_keeps_uncertainty(self):
        row, = detect_media('[clip.mp4](https://github.com/user-attachments/assets/id)', lambda _: {'content_type': 'image/png'})
        self.assertEqual(row['media_status'], 'non_video')
        row, = detect_media('https://github.com/user-attachments/assets/id', lambda _: {'error': 'HEAD unsupported'})
        self.assertEqual(row['media_status'], 'possible_video')

    def test_deduplication_punctuation_and_malformed_urls(self):
        rows = detect_media('https://[invalid/ [clip](https://example.org/repro.mp4). https://example.org/repro.mp4')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['url'], 'https://example.org/repro.mp4')

    def test_probe_refuses_private_ip_and_redirect_keeps_head_without_auth(self):
        with patch('scripts.media.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
            with self.assertRaises(ValueError):
                _public_url('http://localhost/video')
        with patch('scripts.media._public_url'):
            request = PublicRedirects().redirect_request(Request('https://github.com/x', method='HEAD'), None, 302, '', {}, 'https://public.example/x')
        self.assertEqual(request.get_method(), 'HEAD')
        self.assertNotIn('Authorization', request.headers)

    def test_github_file_logs_and_archives_are_not_possible_videos(self):
        text = ('https://github.com/a/game/files/123/debug.log '
                'https://github.com/a/game/files/124/save.zip '
                '[Screenshot.png](https://github.com/user-attachments/assets/screenshot) '
                'https://github.com/a/game/files/125/repro.mp4')
        self.assertEqual([r['media_status'] for r in detect_media(text)], ['non_video', 'non_video', 'non_video', 'video'])


class MediaProbeTests(unittest.TestCase):
    def test_success_is_cached_on_disk_and_uses_unauthenticated_head(self):
        url = 'https://github.com/user-attachments/assets/opaque'
        metadata = {'content_type': 'video/mp4', 'content_disposition': 'attachment; filename="clip.mp4"'}
        response = MagicMock()
        response.__enter__.return_value.headers = {
            'Content-Type': metadata['content_type'],
            'Content-Disposition': metadata['content_disposition'],
        }
        opener = MagicMock()
        opener.open.return_value = response
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            with patch('scripts.media._public_url'), patch('scripts.media.build_opener', return_value=opener):
                self.assertEqual(MediaProbe(cache)(url), metadata)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_method(), 'HEAD')
            self.assertNotIn('Authorization', request.headers)
            cached, = cache.glob('*.json')
            self.assertEqual(json.loads(cached.read_text()), metadata)
            with patch('scripts.media.build_opener', side_effect=AssertionError('cache miss')):
                self.assertEqual(MediaProbe(cache)(url), metadata)

    def test_failure_stays_uncertain_and_is_retried_by_new_probe(self):
        url = 'https://github.com/user-attachments/assets/opaque'
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            probe = MediaProbe(cache)
            with patch('scripts.media._public_url', side_effect=OSError('network unavailable')) as validate:
                row, = detect_media(url, probe)
                self.assertEqual(row['media_status'], 'possible_video')
                self.assertIn('metadata unavailable: OSError', row['evidence'])
                self.assertIn('error', probe(url))
                validate.assert_called_once_with(url)
            self.assertEqual(list(cache.iterdir()), [])
            with patch('scripts.media._public_url', side_effect=ValueError('private address')) as validate:
                self.assertIn('ValueError', MediaProbe(cache)(url)['error'])
                validate.assert_called_once_with(url)

    def test_probe_imports_in_script_and_package_modes(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        url = 'https://example.org/clip'
        metadata = {'content_type': 'video/mp4'}
        with tempfile.TemporaryDirectory() as temporary:
            cached = Path(temporary) / (hashlib.sha256(url.encode()).hexdigest() + '.json')
            cached.write_text(json.dumps(metadata))
            for directory, module in ((scripts.parent, 'scripts.media'), (scripts, 'media')):
                with self.subTest(module=module):
                    code = (f'from {module} import MediaProbe; from pathlib import Path; import json; '
                            f'print(json.dumps(MediaProbe(Path({temporary!r}))({url!r})))')
                    result = subprocess.run([sys.executable, '-c', code], cwd=directory,
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), metadata)
