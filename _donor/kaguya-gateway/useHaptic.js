/**
 * Telegram HapticFeedback 封装
 * 非 Telegram 环境下所有方法为空操作
 */
export function useHaptic() {
  const hf =
    typeof window !== 'undefined' &&
    window.Telegram?.WebApp?.HapticFeedback;

  return {
    light:   () => hf?.impactOccurred?.('light'),
    medium:  () => hf?.impactOccurred?.('medium'),
    heavy:   () => hf?.impactOccurred?.('heavy'),
    tick:    () => hf?.selectionChanged?.(),
    success: () => hf?.notificationOccurred?.('success'),
    error:   () => hf?.notificationOccurred?.('error'),
    warning: () => hf?.notificationOccurred?.('warning'),
  };
}
