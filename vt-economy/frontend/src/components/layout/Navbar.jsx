import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import useAuth from "../../hooks/useAuth";

export default function Navbar() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const initial = useMemo(() => (user?.email ? user.email[0].toUpperCase() : "U"), [user]);

  return (
    <header className="sticky top-0 z-30 w-full bg-slate-900 border-b border-slate-700">
      <div className="h-14 px-4 md:px-6 flex items-center justify-between">
        <Link to="/app/home" className="text-slate-100 font-semibold tracking-wide">
          ⬡ VT Economy
        </Link>

        <div className="relative">
          <button
            type="button"
            onClick={() => setOpen((curr) => !curr)}
            className="h-9 w-9 rounded-full bg-emerald-600 text-white font-bold"
          >
            {initial}
          </button>

          
          {open ? (
            <div className="absolute right-0 mt-2 w-40 rounded-lg border border-slate-700 bg-slate-800 p-2 shadow-lg">

              {/* 👇 ADD THIS */}
              <Link
                to="/app/profile"
                className="block rounded-md px-3 py-2 text-sm text-slate-100 hover:bg-slate-700"
              >
                Profile
              </Link>

              <button
                type="button"
                onClick={logout}
                className="w-full text-left rounded-md px-3 py-2 text-sm text-slate-100 hover:bg-slate-700"
              >
                Logout
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
