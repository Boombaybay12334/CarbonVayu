export default function VTBadge({ score = 0, size = "md" }) {
  const parsed = Number(score) || 0;

  let color = "bg-red-500";
  if (parsed >= 7000) color = "bg-emerald-500";
  else if (parsed >= 4000) color = "bg-amber-500";

  const sizeClass = {
    sm: "text-xs px-2 py-0.5",
    md: "text-sm px-2.5 py-1",
    lg: "text-base px-3 py-1.5",
  }[size];

  return (
    <span className={`${color} ${sizeClass} rounded-full text-white font-mono inline-flex items-center`}>
      {parsed.toLocaleString()} VT
    </span>
  );
}
