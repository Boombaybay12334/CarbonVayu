import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createUserWithEmailAndPassword } from "firebase/auth";
import { auth } from "../../lib/firebase";
import { supabase } from "../../lib/supabase";

const INDIAN_STATES_AND_UTS = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
];

export default function SignupPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("common_man");
  const [stateName, setStateName] = useState("Karnataka");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const cred = await createUserWithEmailAndPassword(auth, email, password);
      const firebaseUser = cred.user;

      let resolvedStateId = null;
      if (role === "state") {
        const { data: stateRow, error: stateError } = await supabase
          .from("states")
          .select("id")
          .eq("name", stateName)
          .maybeSingle();

        if (stateError) {
          throw stateError;
        }
        if (!stateRow?.id) {
          throw new Error("Selected state is not available in database.");
        }

        resolvedStateId = stateRow.id;
      }

      const profilePayload = {
        firebase_uid: firebaseUser.uid,
        email,
        role,
        state_name: role === "state" ? stateName : null,
        state_id: role === "state" ? resolvedStateId : null,
      };

      const { error: profileError } = await supabase
        .from("user_profiles")
        .upsert(profilePayload, { onConflict: "firebase_uid" });

      if (profileError) {
        throw profileError;
      }

      navigate("/app/home", { replace: true });
    } catch (err) {
      setError(err.message || "Signup failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-background">
      
      {/* Decorative Orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/20 rounded-full blur-[100px] animate-pulse-slow"></div>
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-secondary/20 rounded-full blur-[100px] animate-pulse-slow" style={{ animationDelay: '2s' }}></div>

      <div className="w-full max-w-md z-10 animate-slide-up mt-8 mb-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-lg shadow-primary/30 mb-4 animate-float">
            <span className="text-3xl font-display font-bold text-white">V</span>
          </div>
          <h1 className="text-3xl font-display font-bold text-white tracking-tight">Create your account</h1>
          <p className="text-slate-400 mt-2 font-medium">Join the climate dashboard.</p>
        </div>

        <form onSubmit={handleSubmit} className="glass-card p-8 relative overflow-hidden">
          {/* subtle top highlight */}
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-primary to-transparent opacity-50"></div>
          
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5 focus-within:text-primary transition-colors">Email Address</label>
              <input
                type="email"
                autoComplete="username"
                className="w-full rounded-xl border border-white/10 bg-slate-900/50 px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all shadow-inner"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5 focus-within:text-primary transition-colors">Password</label>
              <input
                type="password"
                autoComplete="new-password"
                className="w-full rounded-xl border border-white/10 bg-slate-900/50 px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all shadow-inner"
                placeholder="••••••••"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>

            <fieldset>
              <legend className="block text-sm font-medium text-slate-300 mb-1.5">Role</legend>
              <div className="grid gap-2 grid-cols-3">
                <label className={`cursor-pointer rounded-xl border ${role === "common_man" ? "border-primary/50 bg-primary/10 text-primary" : "border-white/10 bg-slate-900/50 text-slate-300 hover:border-white/20"} p-2 text-xs font-semibold text-center transition-all shadow-inner flex flex-col items-center justify-center`}>
                  <input type="radio" name="role" value="common_man" checked={role === "common_man"} onChange={(event) => setRole(event.target.value)} className="hidden" />
                  Common Man
                </label>
                <label className={`cursor-pointer rounded-xl border ${role === "state" ? "border-primary/50 bg-primary/10 text-primary" : "border-white/10 bg-slate-900/50 text-slate-300 hover:border-white/20"} p-2 text-xs font-semibold text-center transition-all shadow-inner flex flex-col items-center justify-center`}>
                  <input type="radio" name="role" value="state" checked={role === "state"} onChange={(event) => setRole(event.target.value)} className="hidden" />
                  State Gov
                </label>
                <label className={`cursor-pointer rounded-xl border ${role === "admin" ? "border-primary/50 bg-primary/10 text-primary" : "border-white/10 bg-slate-900/50 text-slate-300 hover:border-white/20"} p-2 text-xs font-semibold text-center transition-all shadow-inner flex flex-col items-center justify-center`}>
                  <input type="radio" name="role" value="admin" checked={role === "admin"} onChange={(event) => setRole(event.target.value)} className="hidden" />
                  Central Gov
                </label>
              </div>
            </fieldset>

            {role === "state" ? (
              <div className="animate-fade-in">
                <label className="block text-sm font-medium text-slate-300 mb-1.5 focus-within:text-primary transition-colors">State / UT</label>
                <div className="relative">
                  <select
                    className="w-full rounded-xl border border-white/10 bg-slate-900/50 px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all shadow-inner appearance-none"
                    value={stateName}
                    onChange={(event) => setStateName(event.target.value)}
                  >
                    {INDIAN_STATES_AND_UTS.map((item) => (
                      <option value={item} key={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-400">
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                  </div>
                </div>
              </div>
            ) : null}
            
            {error ? (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2 animate-fade-in">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                {error}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={submitting}
              className="w-full mt-2 bg-gradient-to-r from-primary to-emerald-400 hover:from-emerald-400 hover:to-primary text-white font-semibold rounded-xl px-4 py-3 shadow-lg shadow-primary/25 hover:shadow-primary/40 transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Creating account...
                </span>
              ) : "Sign up"}
            </button>
          </div>
          
          <div className="mt-8 text-center">
            <p className="text-sm text-slate-400">
              Already have an account? <Link to="/login" className="text-primary hover:text-emerald-300 font-medium transition-colors hover:underline underline-offset-4">Sign in</Link>
            </p>
          </div>
        </form>
      </div>
    </main>
  );
}
