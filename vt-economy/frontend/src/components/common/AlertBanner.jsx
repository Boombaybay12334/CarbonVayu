const stylesByType = {
  warning: "border-amber-500/70 bg-amber-500/10 text-amber-200",
  info: "border-sky-500/70 bg-sky-500/10 text-sky-200",
  success: "border-emerald-500/70 bg-emerald-500/10 text-emerald-200",
};

export default function AlertBanner({ alert }) {
  const style = stylesByType[alert?.type] ?? stylesByType.info;

  return (
    <div className={`border-l-4 rounded-md p-3 ${style}`}>
      <p className="text-sm">{alert?.message}</p>
    </div>
  );
}
