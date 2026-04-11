import { useEffect, useRef } from 'react';
import { useHaptic } from '../hooks/useHaptic';

export default function BottomSheet({
  isOpen,
  onClose,
  title,
  children,
  height = '70vh',
}) {
  const sheetRef = useRef(null);
  const haptic = useHaptic();

  const handleClose = () => {
    haptic.light();
    onClose();
  };

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-40 flex flex-col justify-end" onClick={handleClose}>
      <div className="absolute inset-0 bg-primary/5 backdrop-blur-[3px] transition-opacity" />

      <div
        ref={sheetRef}
        className="relative w-full max-w-2xl mx-auto bg-surface rounded-t-sheet shadow-sheet border-t border-white/90 overflow-hidden flex flex-col"
        style={{ height }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-center pt-4 pb-2 shrink-0">
          <div className="h-1.5 w-12 rounded-full bg-secondary/20" />
        </div>

        {title ? (
          <div className="flex items-center justify-between px-8 pb-4 pt-2 shrink-0">
            <h3 className="font-serif text-[22px] font-medium text-primary tracking-tight">
              {title}
            </h3>

            <button
              type="button"
              onClick={handleClose}
              className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-100 bg-white text-secondary shadow-button transition-all hover:bg-gray-50 hover:text-primary active:scale-95 cursor-pointer"
              aria-label="Close"
            >
              <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"></path></svg>
            </button>
          </div>
        ) : null}

        <div
          className="overflow-y-auto px-8 pb-8"
          style={{ maxHeight: `calc(${height} - 80px)` }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
