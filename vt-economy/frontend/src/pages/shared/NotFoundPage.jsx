import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <main className="min-h-screen bg-slate-900 text-slate-100 grid place-items-center p-4">
      <div className="rounded-xl bg-slate-800 border border-slate-700 p-8 text-center">
        <h1 className="text-3xl font-bold">404</h1>
        <p className="text-slate-400 mt-2">This route does not exist yet.</p>
        <Link to="/app/home" className="mt-4 inline-block bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2">
          Back to Home
        </Link>
      </div>
    </main>
  );
}
