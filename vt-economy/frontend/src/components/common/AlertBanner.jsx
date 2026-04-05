export default function AlertBanner({ type = "info", message }) {
  const styles = {
    warning: "bg-yellow-500/10 text-yellow-300 border-yellow-500/30",
    info: "bg-blue-500/10 text-blue-300 border-blue-500/30",
    success: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  };

  const icons = {
    warning: "⚠️",
    info: "ℹ️",
    success: "✅",
  };

  return (
    <div className={`flex items-center gap-3 p-3 rounded-lg border ${styles[type]}`}>
      <span className="text-lg">{icons[type]}</span>
      <p className="text-sm">{message}</p>
    </div>
  );
}