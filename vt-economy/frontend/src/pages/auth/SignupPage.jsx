import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createUserWithEmailAndPassword } from "firebase/auth";
import { auth } from "../../lib/firebase";
import { supabase } from "../../lib/supabase";
import { DUMMY_STATES } from "../../dummy/dummyData";

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

  const matchedStateId = useMemo(() => {
    const match = DUMMY_STATES.find((state) => state.name === stateName);
    return match?.id ?? null;
  }, [stateName]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const cred = await createUserWithEmailAndPassword(auth, email, password);
      const firebaseUser = cred.user;

      const { error: profileError } = await supabase.from("user_profiles").insert({
        firebase_uid: firebaseUser.uid,
        email,
        role,
        state_name: role === "state" ? stateName : null,
        state_id: role === "state" ? matchedStateId : null,
      });

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
    <main className="min-h-screen bg-slate-900 text-slate-100 grid place-items-center p-4">
      <form onSubmit={handleSubmit} className="w-full max-w-xl rounded-xl bg-slate-800 p-6 shadow-md border border-slate-700">
        <h1 className="text-2xl font-bold">Create your account</h1>

        <label className="block mt-5 text-sm text-slate-300">Email</label>
        <input
          type="email"
          autoComplete="username"
          className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <label className="block mt-4 text-sm text-slate-300">Password</label>
        <input
          type="password"
          autoComplete="new-password"
          className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        <fieldset className="mt-4">
          <legend className="text-sm text-slate-300">Role</legend>
          <div className="mt-2 grid gap-2 md:grid-cols-3">
            <label className="rounded-lg border border-slate-600 p-2 text-sm">
              <input type="radio" name="role" value="common_man" checked={role === "common_man"} onChange={(event) => setRole(event.target.value)} className="mr-2" />
              Common Man
            </label>
            <label className="rounded-lg border border-slate-600 p-2 text-sm">
              <input type="radio" name="role" value="state" checked={role === "state"} onChange={(event) => setRole(event.target.value)} className="mr-2" />
              State Government
            </label>
            <label className="rounded-lg border border-slate-600 p-2 text-sm">
              <input type="radio" name="role" value="admin" checked={role === "admin"} onChange={(event) => setRole(event.target.value)} className="mr-2" />
              Central Government
            </label>
          </div>
        </fieldset>

        {role === "state" ? (
          <>
            <label className="block mt-4 text-sm text-slate-300">State / UT</label>
            <select
              className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2"
              value={stateName}
              onChange={(event) => setStateName(event.target.value)}
            >
              {INDIAN_STATES_AND_UTS.map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
            </select>
          </>
        ) : null}

        {error ? <p className="mt-3 text-red-400 text-sm">{error}</p> : null}

        <button
          type="submit"
          disabled={submitting}
          className="mt-5 w-full bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2 disabled:opacity-60"
        >
          {submitting ? "Creating account..." : "Sign up"}
        </button>

        <p className="mt-4 text-sm text-slate-400">
          Already have an account? <Link to="/login" className="text-emerald-400">Sign in</Link>
        </p>
      </form>
    </main>
  );
}
