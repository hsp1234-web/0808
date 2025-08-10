# tools/mock_gemini_processor.py
import argparse
import json
import sys
import time
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Mock Gemini AI 處理工具。")
    parser.add_argument("--command", type=str, required=True, choices=['process', 'list_models', 'validate_key'])
    parser.add_argument("--api-key", type=str)
    parser.add_argument("--audio-file", type=str)
    parser.add_argument("--model", type=str)
    parser.add_argument("--video-title", type=str)
    parser.add_argument("--output-dir", type=str)
    args = parser.parse_args()

    if args.command == 'validate_key':
        # Always succeed
        print(json.dumps({"status": "success", "message": "API 金鑰有效 (模擬)。"}), flush=True)
        sys.exit(0)

    elif args.command == 'list_models':
        # Return a mock list of models
        mock_models = [
            {"id": "models/gemini-1.5-flash-latest", "name": "Gemini 1.5 Flash (模擬)"},
            {"id": "models/gemini-pro", "name": "Gemini Pro (模擬)"}
        ]
        print(json.dumps(mock_models), flush=True)
        sys.exit(0)

    elif args.command == 'process':
        # Simulate processing and return a mock result
        time.sleep(1) # Simulate work
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)

        sanitized_title = args.video_title.replace(" ", "_")[:20] if args.video_title else "mock_video"
        timestamp = time.strftime("%Y%m%d-%H%M%S")

        # Create a dummy HTML report file
        html_report_path = output_dir / f"{sanitized_title}_{timestamp}_AI_Report.html"
        html_report_path.write_text(f"<h1>Mock AI Report for {args.video_title}</h1><p>This is a mock report.</p>", encoding='utf-8')

        result = {
            "type": "result",
            "status": "completed",
            "html_report_path": str(html_report_path), # The frontend looks for html_report_path
            "video_title": args.video_title
        }
        print(json.dumps(result), flush=True)
        sys.exit(0)

if __name__ == "__main__":
    main()
