"""
Client console : le serveur gere l'historique de conversation.

    python scripts/chat_cli.py                         # API locale  (http://localhost:8000)
    python scripts/chat_cli.py --url http://<IP>:8000  # API sur la VM
    python scripts/chat_cli.py --verbose               # affiche aussi les resultats complets des outils

Commandes : /reset (nouvelle conversation), /quit
"""
import argparse
import json

import httpx


def send(client: httpx.Client, url: str, message: str, conversation_id: str | None) -> dict:
    r = client.post(
        f"{url.rstrip('/')}/chat",
        json={"message": message, "conversation_id": conversation_id},
        timeout=60.0,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} : {r.text[:500]}")
    return r.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    conversation_id: str | None = None
    print("Agent P059 — /reset pour recommencer, /quit pour sortir.\n")
    with httpx.Client() as client:
        while True:
            try:
                message = input("toi > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not message:
                continue
            if message == "/quit":
                break
            if message == "/reset":
                conversation_id = None
                print("(nouvelle conversation)\n")
                continue
            try:
                data = send(client, args.url, message, conversation_id)
            except Exception as e:  # noqa: BLE001
                print(f"[erreur] {e}\n")
                continue
            for t in data.get("trace", []):
                print(f"  [outil] {t['tool_called']}({json.dumps(t['args'], ensure_ascii=False)})")
                if args.verbose:
                    print(f"          -> {json.dumps(t['result'], ensure_ascii=False)}")
            print(f"agent > {data['final_response']}\n")
            conversation_id = data["conversation_id"]


if __name__ == "__main__":
    main()
