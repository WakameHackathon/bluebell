"""Pure byte transforms. Host must authorize access, persist and register outputs.
No filesystem/network access. Does not assess visual truth or readability.
"""
from io import BytesIO
import hashlib
import warnings
from PIL import Image

MAX_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 24_000_000

class ImageFailure(ValueError):
    pass

def _decode(blob, declared_format):
    if not isinstance(blob, bytes) or not blob or len(blob) > MAX_BYTES:
        raise ImageFailure('input_size_or_type')
    if declared_format not in ('JPEG', 'PNG'):
        raise ImageFailure('unsupported_format')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            im = Image.open(BytesIO(blob))
            if im.format != declared_format:
                raise ImageFailure('format_mismatch')
            if getattr(im, 'n_frames', 1) != 1:
                raise ImageFailure('animated_unsupported')
            if im.width * im.height > MAX_PIXELS:
                raise ImageFailure('pixel_limit')
            im.verify()
            im = Image.open(BytesIO(blob))
            im.load()
            return im
    except ImageFailure:
        raise
    except Exception as exc:
        raise ImageFailure('decode_failure') from exc

def inspect_image(blob, declared_format):
    im = _decode(blob, declared_format)
    return {'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob),
            'format': im.format, 'width': im.width, 'height': im.height,
            'mode': im.mode, 'orientation': im.getexif().get(274, 1)}

def derive_image(blob, declared_format, operation, *, max_bytes=None,
                 clockwise=None, metadata_removal_approved=False):
    before = inspect_image(blob, declared_format)
    im = _decode(blob, declared_format)
    if operation not in ('compress', 'rotate'):
        raise ImageFailure('unsupported_operation')
    if operation == 'compress':
        if declared_format != 'JPEG' or type(max_bytes) is not int or max_bytes < 1:
            raise ImageFailure('compression_arguments')
        if len(blob) <= max_bytes:
            return {'state': 'unchanged', 'source': before, 'output': None, 'blob': None}
    if operation == 'rotate' and (type(clockwise) is not int or clockwise not in (90,180,270)):
        raise ImageFailure('rotation_arguments')
    if metadata_removal_approved is not True:
        raise ImageFailure('metadata_permission_required')
    if before['orientation'] != 1:
        raise ImageFailure('orientation_requires_host_resolution')
    if im.mode not in ('RGB', 'L') or any(k in im.info for k in ('icc_profile','transparency','gamma','srgb','chromaticity')):
        raise ImageFailure('color_or_transparency_unsupported')
    # Copy pixels to remove metadata without mutating input bytes.
    clean = Image.frombytes(im.mode, im.size, im.tobytes())
    if operation == 'rotate':
        method = {90: Image.Transpose.ROTATE_270,180: Image.Transpose.ROTATE_180,270: Image.Transpose.ROTATE_90}[clockwise]
        out = BytesIO(); clean.transpose(method).save(out, format='PNG')
        result = out.getvalue(); fmt = 'PNG'; params = {'clockwise': clockwise}
    else:
        result = None
        for quality in (90,80,70,60,50,40):
            out = BytesIO(); clean.save(out, format='JPEG', quality=quality, optimize=True)
            candidate = out.getvalue()
            if len(candidate) <= max_bytes:
                result = candidate; break
        if result is None:
            raise ImageFailure('cannot_meet_size_limit')
        fmt = 'JPEG'; params = {'quality': quality, 'max_bytes': max_bytes, 'resized': False}
    after = inspect_image(result, fmt)
    return {'state': 'derived', 'source': before, 'output': after, 'blob': result,
            'operation': operation, 'parameters': params, 'metadata': 'removed',
            'readability': 'pending'}
