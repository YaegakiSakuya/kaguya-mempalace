These files are donor code from the legacy private repository YaegakiSakuya/kaguya-gateway.

Use them as reference for:
1. SSE event protocol: processing / thinking / replying / done
2. Realtime current-process panel
3. History panel showing cot, response, processing metadata, and tool pills
4. Bottom sheet / page shell / tokens styling

Do not restore the old backend architecture wholesale.
Port the useful frontend and SSE protocol into the current kaguya-mempalace inspector stack.

Current target repo facts:
- The current working repo on this server is kaguya-mempalace.
- Existing inspector backend lives under app/inspector/.
- Existing main runtime entry is app/main.py.
- Existing LLM tool loop is app/llm/client.py.

Primary goal:
Build a miniapp-style realtime panel inside the current repo, reusing these donor files where practical.
