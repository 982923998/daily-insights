import http.server
import json
import os
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

# Global state for task logs
task_logs = {}
active_processes = {}
log_queues = {}
log_lock = threading.Lock()


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
        dates = set()
        if os.path.isdir(DATA_DIR):
            for f in os.listdir(DATA_DIR):
                if f.endswith('-ai.json'):
                    dates.add(f[:-len('-ai.json')])
                elif f.endswith('-autism.json'):
                    dates.add(f[:-len('-autism.json')])
        self._json_response({"dates": sorted(dates, reverse=True)})

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

        # Send existing logs first
        with log_lock:
            # Force immediate flush to tell client we are connected
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

        # Keep connection open for new logs
        try:
            while True:
                try:
                    line = client_queue.get(timeout=5)  # 5s timeout keep-alive
                    if line is None:  # End of stream signal
                        self.wfile.write(f"data: {json.dumps({'status': 'done'})}\n\n".encode('utf-8'))
                        self.wfile.flush()
                        break
                    self.wfile.write(f"data: {json.dumps({'log': line})}\n\n".encode('utf-8'))
                    self.wfile.flush()
                except queue.Empty:
                    # Send keep-alive comment
                    try:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    # Check if process is dead and queue is empty
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
        if mode not in ("ai", "autism", "all"):
            self._json_response({"error": "mode must be ai, autism, or all"}, 400)
            return

        task_key = f"fetch_{mode}"
        with log_lock:
            if task_key in active_processes and active_processes[task_key].poll() is None:
                self._json_response({"status": "already_running", "mode": mode})
                return

            # Clear old logs and write a server-side bootstrap line so UI gets immediate feedback.
            start_log = f"[{datetime.now().strftime('%H:%M:%S')}] [SERVER] Fetch task accepted: mode={mode}"
            task_logs[task_key] = [start_log]

            try:
                # Create process
                proc = subprocess.Popen(
                    [FETCH_SCRIPT, mode],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,  # Line buffered
                    cwd=PROJECT_DIR,
                )
            except Exception as exc:
                err = f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] Failed to start fetch process: {exc}"
                task_logs[task_key].append(err)
                self._json_response({"status": "error", "mode": mode, "error": str(exc)}, 500)
                return

            active_processes[task_key] = proc

            # Start log reader thread
            threading.Thread(target=self._read_process_logs, args=(task_key, proc), daemon=True).start()

        self._json_response({"status": "started", "mode": mode})

    def _read_process_logs(self, task_key, proc):
        for line in iter(proc.stdout.readline, ''):
            clean_line = line.rstrip()
            if not clean_line:
                continue
            if self._is_info_log(clean_line):
                continue

            with log_lock:
                if task_key not in task_logs: task_logs[task_key] = []
                task_logs[task_key].append(clean_line)

                if task_key in log_queues:
                    for q in log_queues[task_key]:
                        q.put(clean_line)

    @staticmethod
    def _is_info_log(line):
        """过滤 INFO 级别日志，保留 WARN/ERROR/工具调用/进度等"""
        import re
        # 常见 INFO 格式：[INFO]、INFO[0000]、level=info、"level":"info"
        if re.search(r'\[INFO\]|\bINFO\[|\blevel=info\b|"level"\s*:\s*"info"', line, re.IGNORECASE):
            return True
        # opencode 内部 info 行通常以 "INFO " 开头（大写）
        if re.match(r'^INFO\s', line):
            return True
        return False
        
        proc.stdout.close()
        proc.wait()
        
        # Signal end of stream
        with log_lock:
            if task_key in log_queues:
                for q in log_queues[task_key]:
                    q.put(None)  # Sentinel

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
        # Suppress request logs to keep console clean, or keep them if preferred
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def main():
    port = 8080
    os.makedirs(DATA_DIR, exist_ok=True)
    server = http.server.ThreadingHTTPServer(("", port), DailyNewsHandler)
    print(f"Server running at http://localhost:{port}")
    print(f"  Web UI:  http://localhost:{port}/")
    print(f"  Data:    http://localhost:{port}/data/")
    print(f"  Logs:    http://localhost:{port}/api/events?mode=ai")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
