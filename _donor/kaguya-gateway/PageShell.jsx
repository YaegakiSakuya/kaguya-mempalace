export default function PageShell({ children, className = '' }) {
  return (
    <div
      className={`min-h-screen bg-bg text-primary ${className}`}
      style={{
        paddingTop: 'env(safe-area-inset-top, 0px)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
    >
      {children}
    </div>
  );
}
