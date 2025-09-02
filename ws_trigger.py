import websocket
import json
import sys

def send_ws_message(port, message_type, task_id):
    ws_url = f"ws://127.0.0.1:{port}/api/ws"
    ws = websocket.create_connection(ws_url)

    message = {
        "type": message_type,
        "payload": {
            "task_id": task_id
        }
    }

    print(f"Connecting to {ws_url}...")
    ws.send(json.dumps(message))
    print(f"Sent message: {json.dumps(message)}")

    # Wait for a response (optional, good for debugging)
    # result = ws.recv()
    # print(f"Received: {result}")

    ws.close()
    print("Connection closed.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python ws_trigger.py <port> <message_type> <task_id>")
        sys.exit(1)

    port = sys.argv[1]
    message_type = sys.argv[2]
    task_id = sys.argv[3]

    send_ws_message(port, message_type, task_id)
