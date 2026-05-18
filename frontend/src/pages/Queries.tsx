import { useRef, useState } from "react";
import { Loader2, MessagesSquare, Send } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { ChatMessage } from "@/types/api";

export function QueriesPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionRef = useRef<string | undefined>(undefined);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    const next = [...messages, { role: "user", content: input.trim() } as ChatMessage];
    setMessages(next);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const resp = await api.chatHistory({ messages: next, session_id: sessionRef.current });
      sessionRef.current = resp.session_id;
      setMessages([...next, { role: "assistant", content: resp.reply }]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Chat call failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
          Section 6.4 · Persistent GraphRAG Chat
        </div>
        <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
          Talk to My History
        </h1>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          <MessagesSquare className="h-4 w-4 text-hud-glow" />
          <CardTitle>Session</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 space-y-3">
            {messages.length === 0 && (
              <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hud-textFaint">
                Awaiting query…
              </div>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "rounded-md border border-hud-glow/30 bg-hud-glow/5 px-4 py-3"
                    : "prose-hud rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3"
                }
              >
                <div className="mb-1 font-mono text-[10px] uppercase tracking-[0.25em] text-hud-textFaint">
                  {m.role}
                </div>
                {m.role === "assistant" ? (
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                ) : (
                  <div className="text-hud-text">{m.content}</div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-hud-textDim">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-hud-glow" /> thinking…
              </div>
            )}
          </div>

          <form onSubmit={send} className="flex gap-3">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything about your own history…"
              className="flex-1 rounded-md border border-hud-line bg-hud-panel/40 px-4 py-2.5 font-mono text-[13px] text-hud-text placeholder:text-hud-textFaint focus:border-hud-glow focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading}
              className="neon-btn rounded-md px-5 font-display text-[12px] uppercase tracking-[0.22em] disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
          {error && <div className="mt-3 text-sm text-hud-warn">{error}</div>}
        </CardContent>
      </Card>
    </div>
  );
}
