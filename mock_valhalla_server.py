import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

class MockValhallaHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Print logs to terminal
        print(f"[Mock Valhalla] {self.address_string()} - {format % args}")

    def do_POST(self):
        if self.path == "/route":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
            except Exception:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Bad Request: Invalid JSON")
                return

            if "locations" not in data or not data["locations"]:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Bad Request: Missing locations")
                return

            # Check for avoid_locations configuration
            avoid = data.get("avoid_locations", [])
            if avoid:
                print(f"[Mock Valhalla] Route request WITH avoidance/road-closure exclusion.")
                response_data = {
                    "trip": {
                        "legs": [{"shape": [
                            [12.945818, 77.5275517],
                            [12.943000, 77.525000],
                            [12.940000, 77.520000],
                            [12.930000, 77.518000],
                            [12.936842, 77.522105]
                        ]}],
                        "summary": {"length": 15.2}
                    }
                }
            else:
                print(f"[Mock Valhalla] Route request WITHOUT exclusion.")
                response_data = {
                    "trip": {
                        "legs": [{"shape": [
                            [12.945818, 77.5275517],
                            [12.939000, 77.524000],
                            [12.936842, 77.522105]
                        ]}],
                        "summary": {"length": 10.5}
                    }
                }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/route":
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Bad Request: Empty Payload")
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    port = 8002
    print(f"Starting Mock Valhalla Routing Server on port {port}...")
    server = HTTPServer(('localhost', port), MockValhallaHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Mock Valhalla server stopped.")

if __name__ == "__main__":
    run_server()
