import { Menu } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";

export default function Sidebar({ isOpen, setIsOpen }) {
  const navigate = useNavigate();
  const location = useLocation();

  const items = [
    { name: "Home", path: "/app/home" },
    { name: "Explore VT", path: "/app/explore" },
    { name: "National Visuals", path: "/app/national-visuals" },
    { name: "Leaderboard", path: "/app/leaderboard" },
    { name: "Projects", path: "/app/projects" },
  ];

  return (
    <>
      {/* Toggle */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed top-4 z-[100] bg-slate-800 p-2 rounded-lg border border-white/10 transition-all duration-300
        ${isOpen ? "left-72" : "left-4"}`}
      >
        <Menu size={20} />
      </button>

      {/* Sidebar */}
      <div
        className={`fixed top-0 left-0 h-screen w-64 bg-slate-900 border-r border-white/10 p-5 z-40
        transform transition-transform duration-300
        ${isOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <h1 className="text-xl font-bold text-green-400 mb-8 mt-10">
          VT Economy
        </h1>

        <nav className="space-y-3">
          {items.map((item) => {
            const isActive = location.pathname === item.path;

            return (
              <div
                key={item.name}
                onClick={() => navigate(item.path)}
                className={`p-2 rounded-lg cursor-pointer transition ${
                  isActive
                    ? "bg-green-500/20 text-green-400"
                    : "text-gray-300 hover:text-green-400 hover:bg-green-500/10"
                }`}
              >
                {item.name}
              </div>
            );
          })}
        </nav>
      </div>
    </>
  );
}