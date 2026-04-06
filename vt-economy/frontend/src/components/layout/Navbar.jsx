import { useNavigate, useLocation } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../../context/AuthContext";

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, profile } = useAuth();

  const [open, setOpen] = useState(false);

  const items = [
    { name: "Home", path: "/app/home" },
    { name: "Explore", path: "/app/explore" },
    { name: "National Visuals", path: "/app/national-visuals" },
    { name: "Leaderboard", path: "/app/leaderboard" },
    { name: "Projects", path: "/app/projects" },
  ];

  const userInitial = profile?.name?.charAt(0)?.toUpperCase() || "U";

  return (
    <div className="w-full bg-slate-900/70 backdrop-blur-md border-b border-white/10 px-8 py-4 flex items-center">
      
      {/* LEFT: Logo */}
      <h1
        onClick={() => navigate("/app/home")}
        className="text-xl font-bold text-green-400 cursor-pointer"
      >
        VT Economy
      </h1>

      {/* RIGHT SIDE (push everything right) */}
      <div className="ml-auto flex items-center gap-8">
        
        {/* Nav Items */}
        <div className="flex gap-8">
          {items.map((item) => {
            const isActive = location.pathname === item.path;

            return (
              <p
                key={item.name}
                onClick={() => navigate(item.path)}
                className={`cursor-pointer transition relative ${
                  isActive
                    ? "text-green-400 font-semibold"
                    : "text-gray-300 hover:text-green-400"
                }`}
              >
                {item.name}

                {isActive && (
                  <span className="absolute left-0 -bottom-1 w-full h-[2px] bg-green-400"></span>
                )}
              </p>
            );
          })}
        </div>

        {/* USER AVATAR */}
        <div className="relative">
          <div
            onClick={() => setOpen(!open)}
            className="w-10 h-10 flex items-center justify-center rounded-full bg-green-500 text-black font-bold cursor-pointer"
          >
            {userInitial}
          </div>

          {/* DROPDOWN */}
          {open && (
            <div className="absolute right-0 mt-2 w-32 bg-slate-800 border border-white/10 rounded-lg shadow-lg">
              
              <div
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
                className="px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 cursor-pointer"
              >
                Logout
              </div>

            </div>
          )}
        </div>

      </div>
    </div>
  );
}