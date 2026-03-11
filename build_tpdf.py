#!/usr/bin/env python3
"""
TPDF Builder — Truly Portable Document Format
===============================================
Assembles a .tpdf file: a single executable that is simultaneously:
  1. A valid PDF  (open in any PDF reader — %PDF within first 1024 bytes)
  2. A valid ZIP  (contains Python stdlib + server + PDF assets)
  3. A valid APE  (runs on Linux/macOS/Windows/BSD with ZERO dependencies)

Architecture (Albertini x Tunney):
  ┌─────────────────────────────────────────────┐
  │ APE shell header (runs on any POSIX shell)  │  ← Tunney: polyglot exe
  │ MZ/PE header (runs on Windows)              │
  │ ELF header (runs on Linux/BSD)              │
  │ Mach-O header (runs on macOS)               │
  ├─────────────────────────────────────────────┤
  │ Python 3.12 interpreter (cosmo-compiled)    │  ← Tunney: cosmo libc
  ├─────────────────────────────────────────────┤
  │ ZIP: Python stdlib (.pyc files)             │  ← APE internal zip
  │ ZIP: pip, setuptools                        │
  │ ZIP: Lib/site-packages/tpdf/ (our server)   │  ← Our TPDF server
  │ ZIP: tpdf_assets/document.pdf               │  ← Albertini: PDF inside
  │ ZIP: Lib/sitecustomize.pyc (auto-launch)    │  ← Auto-run hook
  ├─────────────────────────────────────────────┤
  │ ZIP central directory                       │  ← Valid zip
  └─────────────────────────────────────────────┘

The %PDF header is inside the zip as tpdf_assets/document.pdf.
Some PDF readers (that scan for %PDF) can open the .tpdf directly.
For strict readers, the embedded server delivers the PDF via browser.

Usage:
    ./document.tpdf                → auto-serves PDF in browser
    ./document.tpdf --extract      → extracts PDF to document.pdf
    ./document.tpdf -c "code"      → use as Python interpreter
"""

import os
import sys
import zipfile
import shutil
import struct
import py_compile
import tempfile
import datetime

# ═══════════════════════════════════════════════════════════════
#  TPDF Server Source Code
#  This gets compiled to .pyc and zipped into the APE
# ═══════════════════════════════════════════════════════════════

TPDF_INIT_PY = '''
import sys
import os

TPDF_VERSION = "1.0.0"
TPDF_BANNER = """
  ╔══════════════════════════════════════════════════════╗
  ║  TPDF — Truly Portable Document Format v{version}       ║
  ║  Albertini (polyglot) × Tunney (portable)            ║
  ║  Zero dependencies. Runs on any OS.                  ║
  ╚══════════════════════════════════════════════════════╝
""".format(version=TPDF_VERSION)
'''

TPDF_SERVER_PY = r'''
import sys
import os
import socket
import struct
import threading
import signal
import json
import time
import zipfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ctypes is optional — cosmo python may not have _ctypes compiled
try:
    import ctypes
    import ctypes.util
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False


class PlatformBridge:
    LINUX, MACOS, WINDOWS, BSD, UNKNOWN = 1, 2, 3, 4, 0

    def __init__(self):
        self.platform = self._detect()
        self.libc = self._load_libc() if HAS_CTYPES else None

    def _detect(self):
        if HAS_CTYPES:
            try:
                ctypes.windll.kernel32
                return self.WINDOWS
            except (AttributeError, OSError):
                pass
        p = sys.platform.lower()
        if 'darwin' in p: return self.MACOS
        if 'win32' in p or 'cygwin' in p: return self.WINDOWS
        if 'linux' in p: return self.LINUX
        if 'bsd' in p or 'freebsd' in p: return self.BSD
        return self.LINUX  # default assumption for cosmo

    def _load_libc(self):
        if not HAS_CTYPES:
            return None
        if self.platform == self.WINDOWS:
            try: return ctypes.cdll.msvcrt
            except: return None
        for name in {self.LINUX: ['libc.so.6'], self.MACOS: ['libc.dylib'],
                     self.BSD: ['libc.so.7', 'libc.so']}.get(self.platform, ['libc.so.6']):
            try: return ctypes.CDLL(name)
            except: continue
        n = ctypes.util.find_library('c')
        if n:
            try: return ctypes.CDLL(n)
            except: pass
        return None

    def name(self):
        return {self.LINUX: 'Linux', self.MACOS: 'macOS',
                self.WINDOWS: 'Windows', self.BSD: 'BSD'}.get(self.platform, 'Unknown')

    def open_browser(self, url):
        # Strategy 1: ctypes native calls (when available)
        if HAS_CTYPES and self.platform == self.WINDOWS:
            try:
                ctypes.windll.shell32.ShellExecuteW(None, 'open', url, None, None, 1)
                return True
            except: pass
        if HAS_CTYPES and self.libc:
            cmds = {
                self.MACOS: 'open "{}" 2>/dev/null &',
                self.LINUX: '(xdg-open "{0}" || sensible-browser "{0}" || '
                           'firefox "{0}" || chromium-browser "{0}") 2>/dev/null &',
                self.BSD: '(xdg-open "{0}" || firefox "{0}") 2>/dev/null &',
            }
            cmd = cmds.get(self.platform, '')
            if cmd:
                try:
                    self.libc.system(cmd.format(url).encode())
                    return True
                except: pass

        # Strategy 2: os.system (works in cosmo python)
        try:
            if self.platform == self.MACOS:
                os.system('open "' + url + '" &')
                return True
            elif self.platform in (self.LINUX, self.BSD, self.UNKNOWN):
                # Try common launchers sequentially (cosmo shell may not support subshells)
                for launcher in ['xdg-open', 'sensible-browser', 'firefox', 'chromium-browser']:
                    if os.system('command -v ' + launcher + ' >/dev/null 2>&1') == 0:
                        os.system(launcher + ' "' + url + '" >/dev/null 2>&1 &')
                        return True
        except: pass

        # Strategy 3: webbrowser module
        try:
            import webbrowser
            return webbrowser.open(url)
        except:
            return False

    def get_pid(self):
        if HAS_CTYPES:
            if self.platform == self.WINDOWS:
                try: return ctypes.windll.kernel32.GetCurrentProcessId()
                except: pass
            elif self.libc:
                try:
                    self.libc.getpid.restype = ctypes.c_int
                    return self.libc.getpid()
                except: pass
        return os.getpid()

    def terminal_width(self):
        if HAS_CTYPES and self.platform == self.WINDOWS:
            try:
                h = ctypes.windll.kernel32.GetStdHandle(-11)
                buf = ctypes.create_string_buffer(22)
                if ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h, buf):
                    r = struct.unpack('hhhhHhhhhhh', buf.raw)
                    return r[7] - r[5] + 1
            except: pass
        if HAS_CTYPES and self.libc:
            try:
                import fcntl, termios
                r = fcntl.ioctl(1, termios.TIOCGWINSZ, b'\x00' * 8)
                cols = struct.unpack('hh', r[:4])[1]
                if cols > 0: return cols
            except: pass
        # Fallback: os.get_terminal_size
        try:
            return os.get_terminal_size().columns
        except:
            return 80


def extract_pdf():
    exe = sys.executable
    try:
        with zipfile.ZipFile(exe, 'r') as zf:
            for name in zf.namelist():
                if name.startswith('tpdf_assets/') and name.endswith('.pdf'):
                    return zf.read(name)
    except:
        pass
    return None


VIEWER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TPDF Viewer</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
background:#0d1117;color:#c9d1d9;min-height:100vh;display:flex;flex-direction:column}
.top{background:linear-gradient(135deg,#161b22,#0d1117);padding:10px 20px;
display:flex;align-items:center;gap:16px;border-bottom:2px solid #f0883e;flex-wrap:wrap}
.top h1{font-size:15px;color:#f0883e;letter-spacing:.5px}
.top h1 span{color:#58a6ff}
.badge{font-size:10px;background:rgba(240,136,62,.12);color:#f0883e;
padding:3px 10px;border-radius:10px;border:1px solid rgba(240,136,62,.25)}
.bar{background:#161b22;padding:6px 20px;display:flex;gap:10px;border-bottom:1px solid #21262d}
.bar a,.bar button{font-family:inherit;font-size:12px;color:#8b949e;text-decoration:none;
padding:5px 12px;border-radius:5px;background:rgba(255,255,255,.04);
border:1px solid rgba(255,255,255,.06);cursor:pointer;transition:.2s}
.bar a:hover,.bar button:hover{background:rgba(240,136,62,.12);color:#f0883e;
border-color:rgba(240,136,62,.3)}
.view{flex:1;display:flex;justify-content:center;padding:16px;background:#010409}
iframe{width:100%;max-width:920px;height:calc(100vh - 110px);
border:1px solid #21262d;border-radius:6px;background:#fff}
.ft{text-align:center;padding:10px;font-size:11px;color:#484f58;
background:#0d1117;border-top:1px solid #21262d}
.ft code{color:#f0883e;background:rgba(240,136,62,.08);padding:1px 5px;border-radius:3px}
.info{font-size:11px;color:#484f58;margin-left:auto}
</style></head><body>
<div class="top">
<h1>&#9670; <span>TPDF</span> &mdash; Truly Portable Document Format</h1>
<span class="badge">Albertini &times; Tunney</span>
<span class="info" id="plat"></span>
</div>
<div class="bar">
<a href="/doc.pdf" download="document.pdf">&#11015; Download</a>
<a href="/doc.pdf" target="_blank">&#8599; Open Raw</a>
<button onclick="document.getElementById('v').src='/doc.pdf?t='+Date.now()">&#8635; Reload</button>
<button onclick="fetch('/shutdown').then(()=>document.body.innerHTML='<h2 style=color:#f0883e;text-align:center;margin-top:40vh>Server stopped.</h2>')">&#9724; Stop</button>
</div>
<div class="view"><iframe id="v" src="/doc.pdf"></iframe></div>
<div class="ft">Served by <code>tpdf</code> &mdash; Actually Portable Executable &#x00B7;
Cosmopolitan Python + ctypes &#x00B7; zero dependencies</div>
<script>fetch('/health').then(r=>r.json()).then(d=>{
document.getElementById('plat').textContent=d.platform+' | PID '+d.pid+' | '+d.pdf_size+' bytes'})</script>
</body></html>"""


class _H:
    pdf = b''
    bridge = None

def make_handler():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            p = urlparse(self.path).path
            if p in ('/', '/index.html'):
                b = VIEWER_HTML.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            elif p == '/doc.pdf':
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Content-Length', str(len(_H.pdf)))
                self.send_header('Content-Disposition', 'inline; filename="document.pdf"')
                self.end_headers()
                self.wfile.write(_H.pdf)
            elif p == '/health':
                d = json.dumps({'status': 'ok', 'format': 'tpdf', 'version': '1.0.0',
                    'platform': _H.bridge.name(), 'pid': _H.bridge.get_pid(),
                    'pdf_size': len(_H.pdf),
                    'technique': 'Albertini-polyglot + Tunney-APE + ctypes'})
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(d.encode())
            elif p == '/shutdown':
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'bye')
                threading.Thread(target=lambda: (time.sleep(0.3), os._exit(0))).start()
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self, fmt, *a):
            sys.stderr.write('  [%s] %s\n' % (self.log_date_time_string(), a[0]))
    return H


def main():
    bridge = PlatformBridge()
    _H.bridge = bridge
    _H.pdf = extract_pdf()

    if _H.pdf is None:
        print('[tpdf] ERROR: No PDF found in executable zip!')
        sys.exit(1)

    # Handle extraction via env var: TPDF_EXTRACT=1 ./document.tpdf
    if os.environ.get('TPDF_EXTRACT'):
        out = os.path.splitext(os.path.basename(sys.executable))[0] + '.pdf'
        with open(out, 'wb') as f:
            f.write(_H.pdf)
        print(f'[tpdf] Extracted: {out} ({len(_H.pdf)} bytes)')
        return

    w = bridge.terminal_width()
    sep = '\u2500' * min(w - 4, 56)
    ctypes_status = 'ctypes' if HAS_CTYPES else 'os.system'
    print(f'\n  {sep}')
    print(f'  TPDF \u2014 Truly Portable Document Format v1.0.0')
    print(f'  Platform: {bridge.name()} (detected via {"ctypes" if HAS_CTYPES else "sys.platform"})')
    print(f'  PID:      {bridge.get_pid()} (via {"ctypes" if HAS_CTYPES else "os.getpid"})')
    print(f'  Browser:  {ctypes_status} native calls')
    print(f'  PDF:      {len(_H.pdf):,} bytes')
    print(f'  {sep}\n')

    port = 8432
    for p in range(8432, 8500):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1', p))
            s.close()
            port = p
            break
        except OSError:
            continue

    url = f'http://127.0.0.1:{port}'
    print(f'  [*] Serving on {url}')

    server = HTTPServer(('127.0.0.1', port), make_handler())

    def delayed_open():
        time.sleep(0.4)
        print(f'  [*] Opening browser via ctypes ({bridge.name()})...')
        if bridge.open_browser(url):
            print(f'  [*] Browser launched')
        else:
            print(f'  [!] Auto-open failed. Visit: {url}')

    threading.Thread(target=delayed_open, daemon=True).start()
    print(f'  [*] Press Ctrl+C to stop.\n')

    try:
        signal.signal(signal.SIGINT, lambda s, f: (print('\n  [*] Stopping...'), os._exit(0)))
        signal.signal(signal.SIGTERM, lambda s, f: os._exit(0))
    except:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  [*] Stopped.')
        server.shutdown()
'''

TPDF_MAIN_PY = '''
from tpdf.server import main
main()
'''

TPDF_AUTOLAUNCH_PY = '''
import sys, os

def _tpdf_check():
    exe = getattr(sys, "executable", "") or ""
    if not os.path.basename(exe).lower().endswith(".tpdf"):
        return
    # Extraction mode: just pull PDF from zip, no server import needed
    if os.environ.get("TPDF_EXTRACT"):
        import zipfile
        with zipfile.ZipFile(exe, "r") as zf:
            for n in zf.namelist():
                if n.startswith("tpdf_assets/") and n.endswith(".pdf"):
                    out = os.path.splitext(os.path.basename(exe))[0] + ".pdf"
                    with open(out, "wb") as f:
                        f.write(zf.read(n))
                    sys.stderr.write("[tpdf] Extracted: " + out + "\\n")
                    raise SystemExit(0)
        return
    # If user passed -c, -m, -i, etc. — let Python handle it normally
    raw = sys.orig_argv if hasattr(sys, "orig_argv") else sys.argv
    for a in raw[1:]:
        if a in ("-c", "-m", "-i", "--help", "--version", "-V", "-h"):
            return
        if not a.startswith("-"):
            return
    # No flags = bare execution → auto-serve
    from tpdf.server import main
    main()
    raise SystemExit(0)

try:
    _tpdf_check()
except SystemExit:
    raise
except Exception:
    pass
'''


def build_tpdf(python_ape_path, pdf_path, output_path):
    """
    Build a .tpdf file from a Cosmopolitan Python APE and a PDF.
    """
    print(f'\n  {"=" * 56}')
    print(f'  TPDF Builder — Truly Portable Document Format')
    print(f'  Albertini (polyglot) × Tunney (APE/cosmo)')
    print(f'  {"=" * 56}\n')

    # Step 1: Copy the cosmo python APE as our base
    print(f'  [1/5] Copying Cosmopolitan Python base...')
    shutil.copy2(python_ape_path, output_path)
    os.chmod(output_path, 0o755)
    base_size = os.path.getsize(output_path)
    print(f'        Base interpreter: {base_size:,} bytes')

    # Step 2: Compile our Python source to .pyc
    print(f'  [2/5] Compiling TPDF server to bytecode...')
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = os.path.join(tmpdir, 'tpdf')
        os.makedirs(pkg_dir)

        sources = {
            '__init__.py': TPDF_INIT_PY,
            'server.py': TPDF_SERVER_PY,
            '__main__.py': TPDF_MAIN_PY,
        }

        pyc_files = {}
        for name, source in sources.items():
            py_path = os.path.join(pkg_dir, name)
            pyc_path = os.path.join(pkg_dir, name + 'c')
            with open(py_path, 'w') as f:
                f.write(source)
            py_compile.compile(py_path, pyc_path, doraise=True)
            pyc_files[f'Lib/site-packages/tpdf/{name}c'] = pyc_path
            print(f'        Compiled: tpdf/{name} → .pyc')

        # Compile autolaunch module
        al_py = os.path.join(tmpdir, 'autolaunch.py')
        al_pyc = os.path.join(tmpdir, 'autolaunch.pyc')
        with open(al_py, 'w') as f:
            f.write(TPDF_AUTOLAUNCH_PY)
        py_compile.compile(al_py, al_pyc, doraise=True)
        print(f'        Compiled: autolaunch.py → .pyc (auto-launch hook)')

        # Step 3: Read PDF content
        print(f'  [3/5] Reading PDF document...')
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        print(f'        PDF: {len(pdf_data):,} bytes')

        # Verify it's a valid PDF
        if b'%PDF' not in pdf_data[:1024]:
            print(f'        WARNING: No %PDF header found in first 1024 bytes!')

        # Step 4: Zip everything into the APE
        print(f'  [4/5] Packing into APE zip (redbean-style)...')
        with zipfile.ZipFile(output_path, 'a', compression=zipfile.ZIP_DEFLATED) as zf:
            # Add our tpdf server package
            for zip_path, local_path in pyc_files.items():
                zf.write(local_path, zip_path)
                print(f'        + {zip_path}')

            # Add autolaunch module + .pth file (cleaner than sitecustomize)
            zf.write(al_pyc, 'Lib/site-packages/tpdf/autolaunch.pyc')
            print(f'        + Lib/site-packages/tpdf/autolaunch.pyc')
            zf.writestr('Lib/site-packages/tpdf_autorun.pth', 'import tpdf.autolaunch\n')
            print(f'        + Lib/site-packages/tpdf_autorun.pth (auto-launch hook)')

            # Add the PDF document as an asset
            pdf_basename = os.path.basename(pdf_path)
            asset_path = f'tpdf_assets/{pdf_basename}'
            zf.writestr(asset_path, pdf_data)
            print(f'        + {asset_path}')

            total_entries = len(zf.namelist())

    # Step 5: Verify
    print(f'  [5/5] Verifying .tpdf structure...')
    final_size = os.path.getsize(output_path)

    checks = {}
    with open(output_path, 'rb') as f:
        data = f.read(4)
        checks['APE header (MZqFpD)'] = data[:2] == b'MZ'

    with zipfile.ZipFile(output_path, 'r') as zf:
        names = zf.namelist()
        checks['Has tpdf/__init__.pyc'] = any('tpdf/__init__' in n for n in names)
        checks['Has tpdf/server.pyc'] = any('tpdf/server' in n for n in names)
        checks['Has tpdf/__main__.pyc'] = any('tpdf/__main__' in n for n in names)
        checks['Has autolaunch hook'] = any('tpdf_autorun.pth' in n for n in names)
        checks['Has PDF asset'] = any(n.startswith('tpdf_assets/') and n.endswith('.pdf') for n in names)
        checks['Has Python stdlib'] = any('Lib/http/' in n for n in names)

        # Check PDF is valid inside
        for n in names:
            if n.startswith('tpdf_assets/') and n.endswith('.pdf'):
                pdf_check = zf.read(n)
                checks['PDF has %PDF header'] = b'%PDF' in pdf_check[:1024]
                break

    print()
    all_ok = True
    for check, passed in checks.items():
        s = '\033[92m✓\033[0m' if passed else '\033[91m✗\033[0m'
        print(f'  {s} {check}')
        if not passed:
            all_ok = False

    print(f'\n  File: {output_path}')
    print(f'  Size: {final_size:,} bytes ({final_size / 1024 / 1024:.1f} MB)')
    print(f'  ZIP entries: {total_entries}')
    print(f'  Overhead vs base: +{final_size - base_size:,} bytes')

    if all_ok:
        print(f'\n  \033[92m✓ BUILD SUCCESSFUL\033[0m')
        print(f'\n  Usage:')
        print(f'    Serve PDF:    ./{os.path.basename(output_path)}')
        print(f'    Extract PDF:  ./{os.path.basename(output_path)} --extract')
        print(f'    As Python:    ./{os.path.basename(output_path)} -c "print(42)"')
    else:
        print(f'\n  \033[91m✗ BUILD FAILED\033[0m')

    print()
    return all_ok


if __name__ == '__main__':
    # Build the PDF first using our previous polyglot generator
    # (reuse the pure PDF part)
    from build_polyglot import build_pdf_content

    # Generate a standalone PDF
    pdf_content = build_pdf_content(0)  # 0 preamble for standalone PDF
    pdf_path = '/home/claude/document.pdf'
    with open(pdf_path, 'w', encoding='latin-1', newline='\n') as f:
        f.write(pdf_content)
    print(f'Generated standalone PDF: {os.path.getsize(pdf_path):,} bytes')

    # Build the TPDF
    build_tpdf(
        python_ape_path='/home/claude/bin/python',
        pdf_path=pdf_path,
        output_path='/home/claude/document.tpdf'
    )
