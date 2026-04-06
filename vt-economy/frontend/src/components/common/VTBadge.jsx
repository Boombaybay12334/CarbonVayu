export default function VTBadge({ score = 0, size = "md", forceColor }) {
  const parsed = Number(score) || 0;

  let color = "bg-red-500";
  if (parsed >= 500) color = "bg-emerald-500";
  else if (parsed >= 200) color = "bg-amber-500";

  if (forceColor) {
    color = forceColor;
  }

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
