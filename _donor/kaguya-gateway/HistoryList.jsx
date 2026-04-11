import { useState } from 'react';

export default function HistoryList({ items, loading, onRefresh }) {
  const [expanded, setExpanded] = useState(null);

  return (
    <div className="flex h-full flex-col">
      {!items.length ? (
        <div className="flex flex-1 items-center justify-center rounded-card border border-white/40 bg-white/30 p-8 shadow-[0_4px_16px_-8px_rgba(0,0,0,0.02)]">
           <p className="text-sm font-medium text-secondary/60">No history available</p>
        </div>
      ) : null}

      <div className="space-y-3 pb-8 pt-2">
        {items.map((item) => {
          const open = expanded === item.assistant_message_id;
          return (
            <div
              key={item.assistant_message_id}
              className={`group overflow-hidden rounded-[24px] border border-white bg-surface shadow-card transition-all duration-300 ${open ? 'shadow-sheet' : 'hover:-translate-y-0.5 hover:shadow-lg'}`}
            >
              <button
                type="button"
                className="w-full px-5 py-4 text-left cursor-pointer"
                onClick={() => setExpanded(open ? null : item.assistant_message_id)}
              >
                <div className="flex items-center justify-between">
                   <p className="text-[11px] font-bold uppercase tracking-wider text-accent">
                     {new Date(item.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                   </p>
                   <svg className={`text-tertiary transition-transform duration-300 ${open ? 'rotate-180' : ''}`} width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"></path></svg>
                </div>

                <p className="mt-2 text-[10px] font-semibold uppercase tracking-wider text-tertiary">
                  {item.input_tokens ?? '—'} IN / {item.output_tokens ?? '—'} OUT · {item.elapsed_ms ?? ((item.thinking_ms ?? 0) + (item.replying_ms ?? 0))}ms
                </p>
              </button>

              {open ? (
                <div className="border-t border-gray-50 bg-bg/30 px-5 pb-5 pt-4">
                  <div className="space-y-4">
                    {item.cot && item.cot.trim() !== '' && (
                    <div>
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-secondary">COT Trace</p>
                      <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap break-words rounded-[16px] bg-white p-4 text-[12px] leading-[1.7] text-secondary shadow-sm font-serif">
                        {item.cot}
                      </pre>
                    </div>
                    )}
                    <div>
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-primary">Response</p>
                      <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap break-words rounded-[16px] bg-white p-4 text-[13px] leading-[1.8] text-primary shadow-sm font-serif">
                        {item.reply_text || 'No response recorded.'}
                      </pre>
                    </div>
                    {item.processing && Object.keys(item.processing).length > 0 && (
                      <div className="mt-3 border-t border-gray-100/60 pt-3">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-secondary mb-2">Processing</p>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-tertiary">
                          <span>上下文: {item.processing.recent_messages_count ?? '—'} 条消息</span>
                          <span>摘要: {item.processing.rolling_summaries_count ?? '—'} 条</span>
                          <span>记忆: {item.processing.recalled_memories_count ?? '—'} 条 ({item.processing.recall_level ?? '—'})</span>
                        </div>
                        {item.processing.tool_calls?.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-2">
                            {item.processing.tool_calls.map((tc, i) => (
                              <span key={i} className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${tc.success ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'}`}>
                                {tc.name}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
