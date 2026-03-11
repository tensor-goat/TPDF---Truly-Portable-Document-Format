#!/usr/bin/env python3
"""Polyglot PDF Generator — Albertini x Tunney"""
import os, datetime

def build_pdf_content(preamble_size):
    """Build PDF with offsets adjusted for preamble bytes before %PDF."""
    now = datetime.datetime.now().strftime("D:%Y%m%d%H%M%S")
    pdf_lines = []
    offsets = {}

    def add(text):
        pdf_lines.append(text)

    def current_offset():
        # ABSOLUTE offset = preamble + accumulated PDF bytes
        return preamble_size + sum(len(l.encode('latin-1')) for l in pdf_lines)

    page1_stream = (
        "BT\n/F1 28 Tf\n50 750 Td\n(POLYGLOT PDF) Tj\n"
        "0 -35 Td\n/F1 18 Tf\n(Self-Serving Portable Document) Tj\n"
        "0 -50 Td\n/F1 11 Tf\n0.3 0.3 0.3 rg\n"
        "(This file is simultaneously a valid PDF and a valid Python 3 script.) Tj\n"
        "0 -20 Td\n(When opened in a PDF reader, you see this document.) Tj\n"
        "0 -20 Td\n(When run as: python3 portable.pdf -- it serves itself in your browser.) Tj\n"
        "0 -40 Td\n0 0 0 rg\n/F1 14 Tf\n(Inspirations:) Tj\n0 -25 Td\n/F1 11 Tf\n"
        "0.15 0.25 0.5 rg\n"
        "(Ange Albertini \\(corkami\\) -- Polyglot file techniques, PDF internals) Tj\n"
        "0 -18 Td\n(Justine Tunney -- Cosmopolitan Libc, Actually Portable Executable \\(APE\\)) Tj\n"
        "0 -35 Td\n0 0 0 rg\n/F1 14 Tf\n(How It Works:) Tj\n0 -25 Td\n"
        "/F1 11 Tf\n0.3 0.3 0.3 rg\n"
        "(1. The PDF header %PDF-1.7 lives inside a Python variable assignment.) Tj\n"
        "0 -18 Td\n(2. Python sees a triple-quoted raw string containing the full PDF source.) Tj\n"
        "0 -18 Td\n(3. PDF readers parse from the %PDF marker, ignoring the Python preamble.) Tj\n"
        "0 -18 Td\n(4. After the PDF %%EOF marker, the Python self-server code follows.) Tj\n"
        "0 -18 Td\n(5. ctypes provides cross-platform native OS calls -- no dependencies.) Tj\n"
        "0 -40 Td\n0.6 0.1 0.1 rg\n/F1 12 Tf\n"
        "(Zero external dependencies. Pure Python 3 standard library + ctypes.) Tj\n"
        "0 -25 Td\n0 0 0 rg\n/F1 10 Tf\n(Page 1 of 3) Tj\nET\n"
    )
    page2_stream = (
        "BT\n/F1 22 Tf\n50 750 Td\n(Architecture and Polyglot Structure) Tj\n"
        "0 -40 Td\n/F1 11 Tf\n0.3 0.3 0.3 rg\n(FILE LAYOUT:) Tj\n0 -22 Td\n/F2 10 Tf\n"
        "(  +-------------------------------------------+) Tj\n0 -14 Td\n"
        "(  | #!/usr/bin/env python3                    |  <-- shebang) Tj\n0 -14 Td\n"
        "(  | PDF=1;_=r\\264\\264\\264                      |  <-- var + raw string) Tj\n0 -14 Td\n"
        "(  | %PDF-1.7                                  |  <-- PDF header) Tj\n0 -14 Td\n"
        "(  | 1 0 obj << /Type /Catalog ... >>          |  <-- PDF objects) Tj\n0 -14 Td\n"
        "(  | ...streams, fonts, pages...               |) Tj\n0 -14 Td\n"
        "(  | %%EOF                                     |  <-- PDF end) Tj\n0 -14 Td\n"
        "(  | \\264\\264\\264                                 |  <-- string close) Tj\n0 -14 Td\n"
        "(  | import ctypes, http.server ...            |  <-- server) Tj\n0 -14 Td\n"
        "(  | serve_pdf\\(\\)                              |  <-- launch) Tj\n0 -14 Td\n"
        "(  +-------------------------------------------+) Tj\n"
        "0 -30 Td\n/F1 11 Tf\n(CTYPES USAGE -- Cross-Platform Native Calls:) Tj\n0 -22 Td\n/F2 10 Tf\n"
        "(  Linux:   libc.so.6  -> system\\(\"xdg-open http://...\"\\)) Tj\n0 -14 Td\n"
        "(  macOS:   libc.dylib -> system\\(\"open http://...\"\\)) Tj\n0 -14 Td\n"
        "(  Windows: kernel32 + shell32 -> ShellExecuteW\\(...\\)) Tj\n0 -14 Td\n"
        "(  BSD:     libc.so   -> system\\(\"xdg-open http://...\"\\)) Tj\n"
        "0 -30 Td\n/F1 11 Tf\n(PLATFORM DETECTION via ctypes:) Tj\n0 -22 Td\n/F2 10 Tf\n"
        "(  try:    ctypes.windll.kernel32  --> Windows) Tj\n0 -14 Td\n"
        "(  except: probe libc.so.6 / libc.dylib --> Linux or macOS) Tj\n"
        "0 -30 Td\n/F1 11 Tf\n0 0 0 rg\n(HTTP server endpoints:) Tj\n0 -22 Td\n/F2 10 Tf\n"
        "0.3 0.3 0.3 rg\n"
        "(  GET /          -> HTML viewer with embedded PDF rendering) Tj\n0 -14 Td\n"
        "(  GET /doc.pdf   -> The raw PDF bytes extracted from self) Tj\n0 -14 Td\n"
        "(  GET /health    -> JSON status for programmatic checks) Tj\n0 -14 Td\n"
        "(  GET /shutdown  -> Graceful server termination) Tj\n"
        "0 -25 Td\n0 0 0 rg\n/F1 10 Tf\n(Page 2 of 3) Tj\nET\n"
    )
    page3_stream = (
        "BT\n/F1 22 Tf\n50 750 Td\n(Philosophy and Credits) Tj\n"
        "0 -40 Td\n/F1 12 Tf\n0.15 0.25 0.5 rg\n"
        "(\"A file format is just a convention. A polyglot file is a reminder) Tj\n"
        "0 -18 Td\n(that conventions are more fragile than we think.\") Tj\n"
        "0 -14 Td\n/F1 10 Tf\n0.5 0.5 0.5 rg\n"
        "(  -- inspired by the spirit of Ange Albertini) Tj\n"
        "0 -35 Td\n/F1 12 Tf\n0.15 0.25 0.5 rg\n"
        "(\"Software should be able to run anywhere. The computer is the) Tj\n"
        "0 -18 Td\n(platform, not the operating system.\") Tj\n"
        "0 -14 Td\n/F1 10 Tf\n0.5 0.5 0.5 rg\n"
        "(  -- inspired by the spirit of Justine Tunney) Tj\n"
        "0 -45 Td\n0 0 0 rg\n/F1 14 Tf\n(What This Proves:) Tj\n0 -25 Td\n"
        "/F1 11 Tf\n0.3 0.3 0.3 rg\n"
        "(1. File formats are overlapping territories, not walled gardens.) Tj\n0 -20 Td\n"
        "(2. A PDF need not be passive -- it can serve itself.) Tj\n0 -20 Td\n"
        "(3. Python stdlib is powerful enough for full self-hosting.) Tj\n0 -20 Td\n"
        "(4. ctypes bridges Python to any OS without compiled extensions.) Tj\n0 -20 Td\n"
        "(5. Portability is a design choice, not a platform feature.) Tj\n"
        "0 -40 Td\n0 0 0 rg\n/F1 14 Tf\n(Usage:) Tj\n0 -25 Td\n/F2 11 Tf\n"
        "(  $ python3 portable.pdf) Tj\n0 -16 Td\n"
        "(  Serving on http://localhost:8432 ...) Tj\n0 -16 Td\n"
        "(  \\(browser opens automatically via ctypes\\)) Tj\n"
        "0 -35 Td\n/F1 10 Tf\n0 0 0 rg\n(Page 3 of 3) Tj\n"
        "0 -25 Td\n/F1 8 Tf\n0.5 0.5 0.5 rg\n"
        "(Generated: " + now + ") Tj\nET\n"
    )

    add("%PDF-1.7\n")
    add("%\xe2\xe3\xcf\xd3\n")

    offsets[1] = current_offset()
    add("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    offsets[2] = current_offset()
    add("2 0 obj\n<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>\nendobj\n")
    offsets[6] = current_offset()
    add("6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n")
    offsets[7] = current_offset()
    add("7 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>\nendobj\n")
    offsets[8] = current_offset()
    add("8 0 obj\n<< /Font << /F1 6 0 R /F2 7 0 R >> >>\nendobj\n")

    streams = [page1_stream, page2_stream, page3_stream]
    stream_obj_nums = [9, 10, 11]
    for stream, obj_num in zip(streams, stream_obj_nums):
        sb = stream.encode('latin-1')
        offsets[obj_num] = current_offset()
        add(f"{obj_num} 0 obj\n<< /Length {len(sb)} >>\nstream\n")
        add(stream)
        if not stream.endswith("\n"):
            add("\n")
        add("endstream\nendobj\n")

    for page_obj, stream_obj in zip([3, 4, 5], stream_obj_nums):
        offsets[page_obj] = current_offset()
        add(f"{page_obj} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {stream_obj} 0 R /Resources 8 0 R >>\nendobj\n")

    xref_offset = current_offset()
    max_obj = max(offsets.keys())
    add("xref\n")
    add(f"0 {max_obj + 1}\n")
    add("0000000000 65535 f \n")
    for obj_num in range(1, max_obj + 1):
        if obj_num in offsets:
            add(f"{offsets[obj_num]:010d} 00000 n \n")
        else:
            add("0000000000 00000 f \n")
    add("trailer\n")
    add(f"<< /Size {max_obj + 1} /Root 1 0 R >>\n")
    add("startxref\n")
    add(f"{xref_offset}\n")
    add("%%EOF\n")

    return "".join(pdf_lines)


def build_polyglot():
    # First, compute the preamble
    preamble_lines = [
        "#!/usr/bin/env python3\n",
        "# -*- coding: latin-1 -*-\n",
        "# Polyglot PDF: valid as both PDF and Python3\n",
        "# Albertini (corkami) x Tunney (cosmopolitan)\n",
        "PDF=1;_=r'''\n",
    ]
    preamble = "".join(preamble_lines)
    preamble_size = len(preamble.encode('latin-1'))

    # Build PDF with correct absolute offsets
    pdf_content = build_pdf_content(preamble_size)
    assert '%PDF-1.7' in pdf_content
    assert '%%EOF' in pdf_content

    # Read server code
    spath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server_code.py')
    with open(spath, 'r') as f:
        server_code = f.read()

    parts = []
    parts.append(preamble)
    parts.append(pdf_content)
    parts.append("'''\n")
    parts.append("# " + "=" * 60 + "\n")
    parts.append("# END OF PDF DATA -- PYTHON SELF-SERVER BELOW\n")
    parts.append("# " + "=" * 60 + "\n")
    parts.append(server_code)

    polyglot = "".join(parts)
    header_pos = polyglot.find('%PDF-1.7')
    assert header_pos < 1024, f"%PDF-1.7 at byte {header_pos}, must be < 1024!"
    return polyglot


def verify_polyglot(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    checks = {
        "Has shebang":        data.startswith(b'#!/usr/bin/env python3'),
        "%PDF within 1024B":  b'%PDF-1.7' in data[:1024],
        "Has %%EOF":          b'%%EOF' in data,
        "Has ctypes code":    b'import ctypes' in data,
        "Has HTTPServer":     b'HTTPServer' in data,
        "Has PlatformBridge": b'PlatformBridge' in data,
        "Has PDF objects":    b'endobj' in data,
        "Has xref table":    b'xref' in data,
        "Has trailer":       b'trailer' in data,
    }
    ok = True
    for c, p in checks.items():
        s = "\033[92m\u2713\033[0m" if p else "\033[91m\u2717\033[0m"
        print(f"  {s} {c}")
        if not p: ok = False

    # Verify xref offset
    si = data.find(b'startxref\n')
    if si > 0:
        chunk = data[si+10:si+30]
        declared_xref = int(chunk.split(b'\n')[0])
        actual_xref = data.find(b'xref\n')
        match = declared_xref == actual_xref
        s = "\033[92m\u2713\033[0m" if match else "\033[91m\u2717\033[0m"
        print(f"  {s} xref offset correct ({declared_xref} == {actual_xref})")
        if not match: ok = False

    size = len(data)
    pdf_offset = data.find(b'%PDF-1.7')
    eof_offset = data.rfind(b'%%EOF')
    print(f"\n  File size:    {size:,} bytes")
    print(f"  PDF offset:   byte {pdf_offset}")
    print(f"  PDF region:   {eof_offset - pdf_offset + 5:,} bytes")
    print(f"  Python code:  ~{size - eof_offset:,} bytes after %%EOF")
    return ok


if __name__ == '__main__':
    output_path = '/home/claude/portable.pdf'
    print("\n" + "=" * 62)
    print("  POLYGLOT PDF GENERATOR")
    print("  Albertini (polyglot) x Tunney (portable)")
    print("=" * 62 + "\n")
    polyglot = build_polyglot()
    with open(output_path, 'w', encoding='latin-1', newline='\n') as f:
        f.write(polyglot)
    os.chmod(output_path, 0o755)
    print("Verifying polyglot structure:\n")
    ok = verify_polyglot(output_path)
    if ok:
        print(f"\n\033[92m  SUCCESS: {output_path}\033[0m\n")
    else:
        print(f"\n\033[91m  VERIFICATION FAILED\033[0m\n")
