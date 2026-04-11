import { useEffect, useMemo, useRef, useState } from 'react';

const DEV_MOCK_INIT = 'dev-mock-init-data';

export function useSSE(baseUrl, initData, onDone) {
  const [status, setStatus] = useState('idle');
  const [thinkingText, setThinkingText] = useState('');
  const [replyText, setReplyText] = useState('');
  const [thinkingMs, setThinkingMs] = useState(0);
  const [replyingMs, setReplyingMs] = useState(0);
  const [stats, setStats] = useState(null);
  const [processingText, setProcessingText] = useState('');
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const statusRef = useRef('idle');
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const canConnect = useMemo(() => {
    const value = (initData || '').trim();
    return value && value !== DEV_MOCK_INIT;
  }, [initData]);

  const resetCurrent = () => {
    setStatus('idle');
    statusRef.current = 'idle';
    setThinkingText('');
    setReplyText('');
    setProcessingText('');
    setThinkingMs(0);
    setReplyingMs(0);
    setStats(null);
  };

  useEffect(() => {
    if (!canConnect) {
      setConnected(false);
      setError('当前为浏览器开发态，未提供可用 Telegram initData，实时流已禁用');
      resetCurrent();
      return undefined;
    }

    const url = `${baseUrl}?init_data=${encodeURIComponent(initData)}`;
    const es = new EventSource(url);

    setError('');

    es.onopen = () => {
      setConnected(true);
      setError('');
    };

    es.addEventListener('processing', (e) => {
      const data = JSON.parse(e.data || '{}');
      if (statusRef.current === 'idle' || statusRef.current === 'done') {
        setThinkingText('');
        setReplyText('');
        setStats(null);
      }
      statusRef.current = 'processing';
      setStatus('processing');
      setProcessingText(data.message || '处理中...');
    });

    es.addEventListener('thinking', (e) => {
      const data = JSON.parse(e.data || '{}');
      if (statusRef.current === 'idle' || statusRef.current === 'done') {
        setThinkingText(data.chunk || '');
        setReplyText('');
        setStats(null);
      } else {
        setThinkingText((prev) => prev + (data.chunk || ''));
      }
      statusRef.current = 'thinking';
      setStatus('thinking');
      setThinkingMs(Number(data.elapsed_ms || 0));
    });

    es.addEventListener('replying', (e) => {
      const data = JSON.parse(e.data || '{}');
      if (statusRef.current === 'idle' || statusRef.current === 'done') {
        setReplyText(data.chunk || '');
        setThinkingText('');
        setStats(null);
      } else {
        setReplyText((prev) => prev + (data.chunk || ''));
      }
      statusRef.current = 'replying';
      setStatus('replying');
      setReplyingMs(Number(data.elapsed_ms || 0));
    });

    es.addEventListener('done', (e) => {
      const data = JSON.parse(e.data || '{}');
      setStatus('done');
      statusRef.current = 'done';
      setStats({
        input_tokens: data.input_tokens ?? null,
        output_tokens: data.output_tokens ?? null,
        thinking_ms: data.thinking_ms ?? null,
        replying_ms: data.replying_ms ?? null,
      });
      if (typeof onDoneRef.current === 'function') onDoneRef.current();
    });

    es.onerror = () => {
      setConnected(false);
      setError('实时流连接中断，正在自动重连...');
    };

    return () => {
      setConnected(false);
      es.close();
    };
  }, [baseUrl, canConnect, initData]);

  return {
    canConnect,
    status,
    processingText,
    thinkingText,
    replyText,
    thinkingMs,
    replyingMs,
    stats,
    connected,
    error,
    resetCurrent,
  };
}
