import { useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import useAuth from "../../hooks/useAuth";

function LinkItem({ to, label, disabled = false }) {
  if (disabled) {
    return (
      <div
        className="opacity-40 cursor-not-allowed rounded-lg px-3 py-2 text-sm text-slate-400"
        title="Coming Soon"
      >
        {label}
      </div>
    );
  }

  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          "rounded-lg px-3 py-2 text-sm transition-colors",
          isActive ? "bg-emerald-600/20 text-emerald-400" : "text-slate-300 hover:bg-slate-800",
        ].join(" ")
      }
    >
      {label}
    </NavLink>
  );
}

export default function Sidebar() {
  const { profile } = useAuth();
  const [open, setOpen] = useState(true);

  const role = profile?.role ?? "common_man";

  const links = useMemo(() => {
    if (role === "state") {
      return [
        { to: "/app/home", label: "Home" },
        { to: "/app/national-visuals", label: "National Visuals" },
        { to: "/app/state/relations", label: "State Relations" },
        { to: "/app/projects", label: "Invest in Projects" },
        { to: "#", label: "State-Level Tools", disabled: true },
        { to: "#", label: "News", disabled: true },
      ];
    }

    if (role === "admin") {
      return [
        { to: "/app/home", label: "Home" },
        { to: "#", label: "National Visuals", disabled: true },
        { to: "#", label: "State Relations", disabled: true },
        { to: "#", label: "Invest in Projects", disabled: true },
        { to: "#", label: "Model Controls", disabled: true },
      ];
    }

    return [
      { to: "/app/home", label: "Home" },
      { to: "/app/explore", label: "How We Calculate VT" },
      { to: "/app/national-visuals", label: "National Visuals" },
      { to: "/app/leaderboard", label: "Leaderboard" },
      { to: "#", label: "News", disabled: true },
    ];
  }, [role]);

  return (
    <aside className="border-r border-slate-700 bg-slate-900/70 md:w-[220px] shrink-0">
      <button
        type="button"
        onClick={() => setOpen((curr) => !curr)}
        className="m-3 rounded-lg border border-slate-700 px-3 py-2 text-slate-200"
      >
        ☰
      </button>

      {open ? (
        <nav className="px-3 pb-4 flex flex-col gap-2">
          {links.map((link) => (
            <LinkItem key={link.label} to={link.to} label={link.label} disabled={link.disabled} />
          ))}
        </nav>
      ) : null}
    </aside>
  );
}
