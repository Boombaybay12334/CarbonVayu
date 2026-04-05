import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "../../lib/firebase";
import useAuth from "../../hooks/useAuth";

export default function LoginPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) {
      navigate("/app/home", { replace: true });
    }
  }, [user, navigate]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      await signInWithEmailAndPassword(auth, email, password);
      navigate("/app/home", { replace: true });
    } catch (err) {
      setError(err.message || "Failed to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-900 text-slate-100 grid place-items-center p-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-xl bg-slate-800 p-6 shadow-md border border-slate-700">
        <h1 className="text-2xl font-bold">Sign in</h1>
        <p className="text-slate-400 mt-2">Access VT Economy dashboard.</p>

        <label className="block mt-5 text-sm text-slate-300">Email</label>
        <input
          type="email"
          className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <label className="block mt-4 text-sm text-slate-300">Password</label>
        <input
          type="password"
          className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        {error ? <p className="mt-3 text-red-400 text-sm">{error}</p> : null}

        <button
          type="submit"
          disabled={submitting}
          className="mt-5 w-full bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2 disabled:opacity-60"
        >
          {submitting ? "Signing in..." : "Sign in"}
        </button>

        <p className="mt-4 text-sm text-slate-400">
          New here? <Link to="/signup" className="text-emerald-400">Create an account</Link>
        </p>
      </form>
    </main>
  );
}
