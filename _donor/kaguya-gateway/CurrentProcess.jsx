import { useState } from 'react';

export default function CurrentProcess({ status, processingText, thinkingText, replyText, thinkingMs, replyingMs, stats }) {
  // idle 时完全隐藏
  if (status === 'idle') return null;

  // processing 状态
  if (status === 'processing') {
    return (
      <div className="mb-4 rounded-card border border-white bg-surface p-5 shadow-card transition-all">
        <p className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-secondary">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary"></span>
          Processing
        </p>
        <p className="mt-2 font-serif text-[13px] text-secondary">{processingText}</p>
      </div>
    );
  }

  // thinking 状态
  if (status === 'thinking') {
    return (
      <div className="mb-4 rounded-card border border-white bg-surface p-5 shadow-card transition-all">
        <p className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-accent">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent shadow-[0_0_8px_rgba(212,112,78,0.7)]"></span>
          Thinking ({(thinkingMs / 1000).toFixed(1)}s)
        </p>
        <pre className="max-h-60 overflow-y-auto whitespace-pre-wrap break-words rounded-[16px] bg-bg/50 p-4 text-[13px] leading-[1.8] text-secondary font-serif">
          {thinkingText}
        </pre>
      </div>
    );
  }

  // replying 状态
  if (status === 'replying') {
    return (
      <div className="mb-4 space-y-3 rounded-card border border-white bg-surface p-5 shadow-card transition-all">
        {thinkingText ? (
          <ThinkingCollapse text={thinkingText} ms={thinkingMs} />
        ) : null}
        <p className="mt-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-primary">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary"></span>
          Replying ({(replyingMs / 1000).toFixed(1)}s)
        </p>
        <pre className="max-h-60 overflow-y-auto whitespace-pre-wrap break-words rounded-[16px] bg-bg/50 p-4 text-[14px] leading-[1.8] text-primary font-serif">
          {replyText}
        </pre>
      </div>
    );
  }

  // done 状态
  return (
    <div className="mb-4 space-y-3 rounded-card border border-white bg-surface p-5 shadow-card transition-all">
      {thinkingText ? (
        <ThinkingCollapse text={thinkingText} ms={stats?.thinking_ms} />
      ) : null}
      <div className="mt-3 flex items-center justify-between border-t border-gray-100/60 pt-3">
        <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-success">
          <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path></svg>
          Completed
        </p>
        <p className="text-[10px] font-semibold uppercase tracking-wider text-tertiary">
          TOKENS: {stats?.input_tokens ?? '—'}/{stats?.output_tokens ?? '—'} · {stats?.thinking_ms ?? 0}ms / {stats?.replying_ms ?? 0}ms
        </p>
      </div>
    </div>
  );
}

function ThinkingCollapse({ text, ms }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="overflow-hidden rounded-[16px] bg-bg/60 transition-all">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-bg cursor-pointer"
        onClick={() => setOpen(!open)}
      >
        <span className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-secondary">
          <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
          Thoughts ({((ms || 0) / 1000).toFixed(1)}s)
        </span>
        <span className="text-[10px] font-bold text-tertiary">{open ? 'HIDE' : 'SHOW'}</span>
      </button>
      {open ? (
        <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap break-words border-t border-white px-4 pb-4 pt-2 text-[12px] leading-[1.7] text-secondary font-serif">
          {text}
        </pre>
      ) : null}
    </div>
  );
}
