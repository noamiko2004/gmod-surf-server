"""Checks whether a surf map looks right for players who don't own CS:S.

Most surf maps were made for Counter-Strike: Source and use its textures. The
server mounts CS:S (server/cfg/mount.cfg), but players who don't own it see
those surfaces as a purple and black checkerboard. A map is fine when every
texture it uses is packed into the .bsp, ships in its Workshop item, or is
part of the content every Garry's Mod player has (Garry's Mod and HL2 .vpk
files). Standard library only.
"""
import io
import lzma
import os
import re
import struct
import zipfile

# A map is taken out when at least this share of its visible surfaces
# would show the checkerboard
MAX_MISSING_SHARE = 0.05

LUMP_ENTITIES, LUMP_TEXDATA, LUMP_TEXINFO, LUMP_FACES = 0, 2, 6, 7
LUMP_GAME, LUMP_PAKFILE, LUMP_TEXSTRINGS, LUMP_TEXTABLE, LUMP_FACES_HDR = 35, 40, 43, 44, 58
SURF_SKY, SURF_SKY2D, SURF_NODRAW = 0x4, 0x2, 0x80
SPRP = int.from_bytes(b"sprp", "big")


# Content every player has ---------------------------------------------------

def vpk_names(path):
    """File names (lowercase, forward slashes) listed in a *_dir.vpk."""
    with open(path, "rb") as f:
        buf = f.read()
    sig, version, tree = struct.unpack_from("<III", buf, 0)
    if sig != 0x55AA1234:
        return set()
    pos = 12 if version == 1 else 28
    end = pos + tree

    def cstr():
        nonlocal pos
        e = buf.index(b"\0", pos)
        s = buf[pos:e].decode("utf-8", "replace")
        pos = e + 1
        return s

    out = set()
    while pos < end:
        ext = cstr()
        if not ext:
            break
        while True:
            folder = cstr()
            if not folder:
                break
            while True:
                name = cstr()
                if not name:
                    break
                (preload,) = struct.unpack_from("<H", buf, pos + 4)
                pos += 18 + preload
                full = f"{name}.{ext}" if folder.strip() == "" else f"{folder}/{name}.{ext}"
                out.add(full.replace("\\", "/").lower())
    return out


def loose_names(root, subdirs=("materials", "models")):
    out = set()
    for sub in subdirs:
        top = os.path.join(root, sub)
        for dirpath, _, names in os.walk(top):
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/").lower()
            out.update(f"{rel}/{n.lower()}" for n in names)
    return out


def base_content(server_dir):
    """Everything a Garry's Mod player has without CS:S: the .vpk files and
    loose materials that ship with the game (addons and downloads excluded)."""
    names = set()
    for sub in ("garrysmod", "sourceengine", "platform"):
        d = os.path.join(server_dir, sub)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if n.endswith("_dir.vpk"):
                try:
                    names |= vpk_names(os.path.join(d, n))
                except (OSError, ValueError, struct.error):
                    pass
    names |= loose_names(os.path.join(server_dir, "garrysmod"))
    return names


def has_base(names):
    """True when the base content was found (otherwise every texture would look missing)."""
    return any(n in names for n in ("materials/tools/toolsnodraw.vmt", "materials/tools/toolsclip.vmt"))


def css_content(css_dir):
    path = os.path.join(css_dir or "", "cstrike", "cstrike_pak_dir.vpk")
    try:
        return vpk_names(path)
    except (OSError, ValueError, struct.error):
        return set()


# BSP reading ---------------------------------------------------------------

def unlzma(data):
    """Valve's LZMA lump format: 'LZMA', real size, packed size, 5 property bytes."""
    if data[:4] != b"LZMA":
        return data
    size, _ = struct.unpack_from("<II", data, 4)
    props = data[12:17]
    d = props[0]
    filt = {"id": lzma.FILTER_LZMA1, "dict_size": struct.unpack_from("<I", props, 1)[0],
            "lc": d % 9, "lp": (d // 9) % 5, "pb": d // 45}
    return lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[filt]).decompress(data[17:])[:size]


class Bsp:
    def __init__(self, buf):
        if buf[:4] != b"VBSP":
            raise ValueError("not a VBSP file")
        self.buf = buf
        self.lumps = [struct.unpack_from("<iiii", buf, 8 + i * 16) for i in range(64)]

    def lump(self, i):
        ofs, length, _, uncompressed = self.lumps[i]
        data = self.buf[ofs:ofs + length]
        return unlzma(data) if uncompressed else data

    def texture_names(self):
        strings, table = self.lump(LUMP_TEXSTRINGS), self.lump(LUMP_TEXTABLE)
        out = []
        for (ofs,) in struct.iter_unpack("<i", table[:len(table) // 4 * 4]):
            end = strings.find(b"\0", ofs)
            out.append(strings[ofs:end if end >= 0 else len(strings)].decode("utf-8", "replace").replace("\\", "/").lower())
        return out

    def face_counts(self):
        """{material name: visible faces using it}"""
        strings = self.texture_names()
        texdata = self.lump(LUMP_TEXDATA)
        names = []
        for i in range(0, len(texdata) - 31, 32):
            (sid,) = struct.unpack_from("<i", texdata, i + 12)
            names.append(strings[sid] if 0 <= sid < len(strings) else "")
        texinfo = self.lump(LUMP_TEXINFO)
        infos = [struct.unpack_from("<ii", texinfo, i + 64) for i in range(0, len(texinfo) - 71, 72)]
        faces = self.lump(LUMP_FACES) or self.lump(LUMP_FACES_HDR)
        counts = {}
        for i in range(0, len(faces) - 55, 56):
            (ti,) = struct.unpack_from("<h", faces, i + 10)
            if ti < 0 or ti >= len(infos):
                continue
            flags, td = infos[ti]
            if flags & (SURF_SKY | SURF_SKY2D | SURF_NODRAW) or td < 0 or td >= len(names) or not names[td]:
                continue
            counts[names[td]] = counts.get(names[td], 0) + 1
        return counts

    def skyname(self):
        m = re.search(rb'"skyname"\s+"([^"]+)"', self.lump(LUMP_ENTITIES))
        return m.group(1).decode("utf-8", "replace").lower() if m else ""

    def static_props(self):
        game = self.lump(LUMP_GAME)
        if len(game) < 4:
            return []
        (count,) = struct.unpack_from("<i", game, 0)
        for i in range(count):
            gid, flags, _, ofs, length = struct.unpack_from("<iHHii", game, 4 + i * 16)
            if gid != SPRP or flags & 1:
                continue
            (n,) = struct.unpack_from("<i", self.buf, ofs)
            return [self.buf[ofs + 4 + k * 128:ofs + 4 + (k + 1) * 128].split(b"\0")[0].decode("utf-8", "replace")
                    .replace("\\", "/").lower() for k in range(max(0, min(n, 4096)))]
        return []

    def pak(self):
        try:
            return zipfile.ZipFile(io.BytesIO(self.lump(LUMP_PAKFILE)))
        except (zipfile.BadZipFile, ValueError):
            return None


# The check ------------------------------------------------------------------

def _vmt_refs(text):
    """Materials and textures a packed .vmt points at."""
    refs = []
    for key, value in re.findall(r'"?(\$basetexture|\$basetexture2|include)"?\s+"?([^"\s}]+)', text, re.I):
        v = value.replace("\\", "/").lower()
        if key.lower() == "include":
            refs.append(v if v.startswith("materials/") else "materials/" + v)
        else:
            refs.append("materials/" + v + ("" if v.endswith(".vtf") else ".vtf"))
    return refs


def check_map(bsp_path, provided, base, css):
    """Returns a report: faces, missing_faces, css_faces, share, missing (names), sky, props.
    provided: files in the map's Workshop item. base: content every player has.
    css: CS:S content (only used to say why something is missing)."""
    with open(bsp_path, "rb") as f:
        bsp = Bsp(f.read())
    pak = bsp.pak()
    packed = {n.replace("\\", "/").lower(): n for n in (pak.namelist() if pak else [])}
    have = set(packed) | set(provided) | base

    def material_ok(path, depth=0):
        if path not in have:
            return False
        if path in packed and path.endswith(".vmt") and depth < 3:
            try:
                text = pak.read(packed[path]).decode("utf-8", "replace")
            except Exception:  # odd compression; trust the file is there
                return True
            for ref in _vmt_refs(text):
                if ref.endswith(".vmt"):
                    if not material_ok(ref, depth + 1):
                        return False
                elif ref not in have:
                    return False
        return True

    counts = bsp.face_counts()
    total = sum(counts.values())
    missing, css_faces, missing_faces = [], 0, 0
    for name, n in counts.items():
        if name.startswith("tools/"):
            continue
        path = f"materials/{name}.vmt"
        if material_ok(path):
            continue
        missing.append(name)
        missing_faces += n
        if path in css:
            css_faces += n
    sky = bsp.skyname()
    sky_ok = not sky or material_ok(f"materials/skybox/{sky}rt.vmt") or material_ok(f"materials/skybox/{sky}_hdrrt.vmt")
    props = [p for p in bsp.static_props() if p and p not in have]
    return {
        "faces": total,
        "missing_faces": missing_faces,
        "css_faces": css_faces,
        "share": missing_faces / total if total else 0.0,
        "missing": sorted(missing),
        "sky": "" if sky_ok else sky,
        "props": sorted(set(props)),
    }


def verdict(report):
    """None when the map is fine, else why it's taken out."""
    if report["share"] < MAX_MISSING_SHARE:
        return None
    pct = round(report["share"] * 100)
    if report["css_faces"] * 2 >= report["missing_faces"]:
        return f"needs Counter-Strike: Source textures ({pct}% of the map shows the purple checkerboard without CS:S)"
    return f"textures missing from the Workshop item ({pct}% of the map shows the purple checkerboard)"
