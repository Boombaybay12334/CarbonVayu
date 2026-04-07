import { useNavigate, useLocation } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import logo from "../../assets/logo.png";

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
    <div className="fixed top-0 left-0 w-full glass-panel z-50 px-8 py-4 flex items-center transition-all duration-300">
      
      {/* LEFT: Logo */}
      <div
        onClick={() => navigate("/app/home")}
        className="flex items-center cursor-pointer group"
      >
        <img 
          src={logo} 
          alt="CarbonVayu Dashboard" 
          className="h-12 w-auto object-contain transition-transform duration-300 group-hover:scale-105 drop-shadow-md"
        />
      </div>

      {/* RIGHT SIDE (push everything right) */}
      <div className="ml-auto flex items-center gap-10">
        
        {/* Nav Items */}
        <div className="flex gap-8">
          {items.map((item) => {
            const isActive = location.pathname === item.path;

            return (
              <div
                key={item.name}
                onClick={() => navigate(item.path)}
                className={`cursor-pointer transition-all duration-300 relative group py-2 ${
                  isActive
                    ? "text-white font-semibold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <span className="relative z-10">{item.name}</span>
                
                {isActive ? (
                  <span className="absolute bottom-0 left-0 w-full h-0.5 bg-gradient-to-r from-primary to-secondary rounded-full shadow-[0_0_8px_rgba(16,185,129,0.5)]"></span>
                ) : (
                  <span className="absolute bottom-0 left-0 w-0 h-0.5 bg-primary/50 rounded-full transition-all duration-300 group-hover:w-full"></span>
                )}
              </div>
            );
          })}
        </div>

        {/* USER AVATAR */}
        <div className="relative">
          <div
            onClick={() => setOpen(!open)}
            className="w-11 h-11 flex items-center justify-center rounded-full bg-slate-800 border-2 border-slate-700 text-white font-display font-bold cursor-pointer hover:border-primary/50 hover:shadow-lg hover:shadow-primary/20 transition-all duration-300"
          >
            {userInitial}
          </div>

           {/* DROPDOWN */}
          {open && (
            <div className="absolute right-0 mt-3 w-40 glass-card animate-slide-up origin-top-right z-50">
              <div className="p-2">
                <div
                  onClick={() => {
                    logout();
                    navigate("/login");
                  }}
                  className="px-4 py-2.5 text-sm font-medium text-red-400 rounded-lg hover:bg-red-500/10 hover:text-red-300 cursor-pointer transition-colors flex items-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="十七 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  Logout
                </div>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}