"""Verifica imagens PE contra o ICO publicado, sem depender do Explorer."""
import io
import struct
import sys
from pathlib import Path
import pefile
from PIL import Image, ImageChops

exe, ico = map(Path, sys.argv[1:3])
pe = pefile.PE(str(exe))
resources = {e.id: e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries}
groups = resources[14].directory.entries
icons = {e.id: e for e in resources[3].directory.entries}
def read(entry):
    d = entry.directory.entries[0].data.struct
    return pe.get_data(d.OffsetToData, d.Size)
reference = Image.open(ico)
expected = reference.ico.sizes()
for group in groups:
    data = read(group)
    _, kind, count = struct.unpack_from('<HHH', data)
    if kind != 1: continue
    seen = set()
    for i in range(count):
        width, height, _, _, _, _, _, ident = struct.unpack_from('<BBBBHHIH', data, 6 + 14*i)
        size = (width or 256, height or 256)
        if size not in expected: continue
        payload = read(icons[ident])
        # Wrap each RT_ICON in an ICO container so Pillow handles PNG and DIB.
        blob = struct.pack('<HHHBBBBHHII', 0, 1, 1, width, height, 0, 0, 1, 32, len(payload), 22) + payload
        actual = Image.open(io.BytesIO(blob)).convert('RGBA')
        wanted = reference.ico.getimage(size).convert('RGBA')
        if (ImageChops.difference(actual.convert('RGB'), wanted.convert('RGB')).getbbox() is not None
                or ImageChops.difference(actual.getchannel('A'), wanted.getchannel('A')).getbbox() is not None):
            raise ValueError(f'Ícone diferente do recurso esperado: {size}')
        seen.add(size)
    if seen == expected:
        print(f'PE com ícone azul validado: {exe.name}, tamanhos={sorted(seen)}')
        sys.exit(0)
raise ValueError(f'Ícone incompleto: esperados {sorted(expected)}')
