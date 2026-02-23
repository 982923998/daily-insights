import http.server
import json
import os
import re
import subprocess
import threading
import time
import queue
from datetime import datetime
from urllib.parse import urlparse, parse_qs

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
WEB_DIR = os.path.join(PROJECT_DIR, "web")
FETCH_SCRIPT = os.path.join(PROJECT_DIR, "scripts", "fetch.sh")
ACADEMIC_SOURCES_DIR = os.path.join(PROJECT_DIR, ".agents", "skills", "academic-search", "sources")
SKILLS_DIR = os.path.join(PROJECT_DIR, ".agents", "skills")

# Global state for task logs
task_logs = {}
active_processes = {}
log_queues = {}
log_lock = threading.Lock()


def parse_frontmatter(filepath):
    """Parse YAML frontmatter (between --- markers) from a markdown file."""
    result = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if match:
            for line in match.group(1).splitlines():
                line = line.strip()
                if ':' in line:
                    key, _, value = line.partition(':')
                    result[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        pass
    return result


def load_domains():
    """Load domain configs and auto-discover from data files.

    Priority: academic-search/sources/{id}.md > skill SKILL.md (domain_* fields) > minimal fallback.
    Any domain ID found in data/ but missing a config gets a default entry.
    """
    # Step 1: explicit configs from academic-search/sources/*.md
    explicit = {}
    if os.path.isdir(ACADEMIC_SOURCES_DIR):
        for fname in sorted(os.listdir(ACADEMIC_SOURCES_DIR)):
            if not fname.endswith('.md'):
                continue
            domain = parse_frontmatter(os.path.join(ACADEMIC_SOURCES_DIR, fname))
            if domain.get('id'):
                explicit[domain['id']] = domain

    # Step 2: skill-level domain configs (skills that declare domain_id in SKILL.md)
    skill_domains = {}
    if os.path.isdir(SKILLS_DIR):
        for skill_name in os.listdir(SKILLS_DIR):
            skill_md = os.path.join(SKILLS_DIR, skill_name, 'SKILL.md')
            if not os.path.isfile(skill_md):
                continue
            meta = parse_frontmatter(skill_md)
            domain_id = meta.get('domain_id')
            if not domain_id:
                continue
            skill_domains[domain_id] = {
                'id': domain_id,
                'label': meta.get('domain_label', domain_id.upper()),
                'category': meta.get('domain_category', domain_id.upper()),
                'color': meta.get('domain_color', '#6366f1'),
                'icon': meta.get('domain_icon', 'layers'),
                'skill': meta.get('name', skill_name),
                'order': meta.get('domain_order', '0'),
            }

    # Step 3: discover domain IDs from data files
    discovered = set()
    if os.path.isdir(DATA_DIR):
        for f in os.listdir(DATA_DIR):
            if not f.endswith('.json'):
                continue
            name = f[:-5]
            parts = name.rsplit('-', 1)
            if len(parts) == 2 and re.match(r'^\d{4}-\d{2}-\d{2}$', parts[0]):
                discovered.add(parts[1])

    # Step 4: merge — explicit wins, then skill_domains, then minimal fallback
    all_domains = dict(explicit)
    for domain_id in discovered:
        if domain_id in all_domains:
            continue
        if domain_id in skill_domains:
            all_domains[domain_id] = skill_domains[domain_id]
        else:
            all_domains[domain_id] = {
                'id': domain_id,
                'label': domain_id.upper(),
                'category': domain_id.upper(),
                'color': '#6366f1',
                'icon': 'layers',
                'skill': 'daily-ai-news',
                'order': '0',
            }

    domains = list(all_domains.values())
    domains.sort(key=lambda d: int(d.get('order', 99)))
    return domains


class DailyNewsHandler(http.server.SimpleHTTPRequestHandler):

    def translate_path(self, path):
        parsed = urlparse(path)
        clean = parsed.path
        if clean.startswith("/data/"):
            return os.path.join(PROJECT_DIR, clean.lstrip("/"))
        rel = clean.lstrip("/")
        return os.path.join(WEB_DIR, rel) if rel else WEB_DIR

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._handle_status()
            return
        if parsed.path == "/api/dates":
            self._handle_dates()
            return
        if parsed.path == "/api/domains":
            self._handle_domains()
            return
        if parsed.path == "/api/events":
            self._handle_events(parsed)
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/fetch":
            self._handle_fetch(parsed)
            return
        self.send_error(404)

    def _handle_status(self):
        status = {}
        with log_lock:
            for k, p in active_processes.items():
                if p.poll() is None:
                    status[k] = "running"
                else:
                    status[k] = "done" if p.returncode == 0 else "error"
        self._json_response(status)

    def _handle_dates(self):
        """Return all dates that have at least one data file."""
        dates = set()
        if os.path.isdir(DATA_DIR):
            for f in os.listdir(DATA_DIR):
                if not f.endswith('.json'):
                    continue
                # Format: YYYY-MM-DD-{id}.json — split off domain id at last hyphen
                name = f[:-5]  # strip .json
                parts = name.rsplit('-', 1)
                if len(parts) == 2 and re.match(r'^\d{4}-\d{2}-\d{2}$', parts[0]):
                    dates.add(parts[0])
        self._json_response({"dates": sorted(dates, reverse=True)})

    def _handle_domains(self):
        """Return domain metadata loaded from academic-search/sources/*.md."""
        domains = load_domains()
        self._json_response({"domains": domains})

    def _handle_events(self, parsed):
        # SSE endpoint
        query = parse_qs(parsed.query)
        mode = query.get("mode", ["ai"])[0]
        task_key = f"fetch_{mode}"

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        with log_lock:
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

            existing = task_logs.get(task_key, [])
            client_queue = queue.Queue()
            if task_key not in log_queues:
                log_queues[task_key] = []
            log_queues[task_key].append(client_queue)

        for line in existing:
            try:
                self.wfile.write(f"data: {json.dumps({'log': line})}\n\n".encode('utf-8'))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

        try:
            while True:
                try:
                    line = client_queue.get(timeout=5)
                    if line is None:
                        self.wfile.write(f"data: {json.dumps({'status': 'done'})}\n\n".encode('utf-8'))
                        self.wfile.flush()
                        break
                    self.wfile.write(f"data: {json.dumps({'log': line})}\n\n".encode('utf-8'))
                    self.wfile.flush()
                except queue.Empty:
                    try:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    with log_lock:
                        proc = active_processes.get(task_key)
                        if proc and proc.poll() is not None and client_queue.empty():
                            break
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with log_lock:
                if task_key in log_queues and client_queue in log_queues[task_key]:
                    log_queues[task_key].remove(client_queue)

    def _handle_fetch(self, parsed):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = {}

        mode = params.get("mode", "ai")

        # Validate: alphanumeric, hyphens, underscores only
        if not re.match(r'^[a-zA-Z0-9_-]+$', mode):
            self._json_response({"error": "invalid mode"}, 400)
            return

        task_key = f"fetch_{mode}"
        with log_lock:
            if task_key in active_processes and active_processes[task_key].poll() is None:
                self._json_response({"status": "already_running", "mode": mode})
                return

            start_log = f"[{datetime.now().strftime('%H:%M:%S')}] [SERVER] Fetch task accepted: mode={mode}"
            task_logs[task_key] = [start_log]

            try:
                proc = subprocess.Popen(
                    [FETCH_SCRIPT, mode],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=PROJECT_DIR,
                )
            except Exception as exc:
                err = f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] Failed to start fetch process: {exc}"
                task_logs[task_key].append(err)
                self._json_response({"status": "error", "mode": mode, "error": str(exc)}, 500)
                return

            active_processes[task_key] = proc
            threading.Thread(target=self._read_process_logs, args=(task_key, proc), daemon=True).start()

        self._json_response({"status": "started", "mode": mode})

    def _read_process_logs(self, task_key, proc):
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        for line in iter(proc.stdout.readline, ''):
            clean_line = ansi_escape.sub('', line.rstrip())
            if not clean_line:
                continue
            if self._is_info_log(clean_line):
                continue
            if len(clean_line) > 500:
                clean_line = clean_line[:500] + '  …[truncated]'
            with log_lock:
                if task_key not in task_logs:
                    task_logs[task_key] = []
                task_logs[task_key].append(clean_line)
                if task_key in log_queues:
                    for q in log_queues[task_key]:
                        q.put(clean_line)

        proc.stdout.close()
        proc.wait()

        with log_lock:
            if task_key in log_queues:
                for q in log_queues[task_key]:
                    q.put(None)  # End-of-stream sentinel

    @staticmethod
    def _is_info_log(line):
        # INFO level markers
        if re.search(r'\[INFO\]|\bINFO\[|\blevel=info\b|"level"\s*:\s*"info"', line, re.IGNORECASE):
            return True
        if re.match(r'^INFO\s', line):
            return True
        # opencode internal bus messages (service=bus, message.part.updated, etc.)
        if re.search(r'service=bus|type=message\.|message\.part\.', line):
            return True
        return False

    def _json_response(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def main():
    port = 8080
    os.makedirs(DATA_DIR, exist_ok=True)
    server = http.server.ThreadingHTTPServer(("", port), DailyNewsHandler)
    print(f"Server running at http://localhost:{port}")
    print(f"  Web UI:   http://localhost:{port}/")
    print(f"  Domains:  http://localhost:{port}/api/domains")
    print(f"  Data:     http://localhost:{port}/data/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
