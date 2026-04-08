import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { supabase } from "../../lib/supabase";

const INDIAN_STATES_AND_UTS = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
];

export default function ProfileRecoveryPage() {
  const navigate = useNavigate();
  const { user, refreshProfile } = useAuth();

  const [role, setRole] = useState("");
  const [stateName, setStateName] = useState("Karnataka");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    if (!user) {
      setError("Session expired. Please sign in again.");
      navigate("/login", { replace: true });
      return;
    }

    if (!role) {
      setError("Please choose a role to continue.");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
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
        firebase_uid: user.uid,
        email: user.email ?? "",
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

      await refreshProfile();
      navigate("/app/home", { replace: true });
    } catch (err) {
      setError(err.message || "Unable to save profile.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-[70vh] grid place-items-center p-4">
      <form onSubmit={handleSubmit} className="w-full max-w-xl rounded-xl bg-slate-900/60 p-6 shadow-md border border-slate-700">
        <h1 className="text-2xl font-bold text-white">Complete Your Profile</h1>
        <p className="mt-2 text-sm text-slate-300">
          Your account needs role setup before you can use dashboard routes.
        </p>

        <fieldset className="mt-5">
          <legend className="text-sm text-slate-300">Select Role</legend>
          <div className="mt-2 grid gap-2 md:grid-cols-3">
            <label className={`rounded-lg border p-2 text-sm cursor-pointer ${role === "common_man" ? "border-emerald-400 text-emerald-300" : "border-slate-600 text-slate-200"}`}>
              <input
                type="radio"
                name="role"
                value="common_man"
                checked={role === "common_man"}
                onChange={(event) => setRole(event.target.value)}
                className="mr-2"
              />
              Common Man
            </label>
            <label className={`rounded-lg border p-2 text-sm cursor-pointer ${role === "state" ? "border-emerald-400 text-emerald-300" : "border-slate-600 text-slate-200"}`}>
              <input
                type="radio"
                name="role"
                value="state"
                checked={role === "state"}
                onChange={(event) => setRole(event.target.value)}
                className="mr-2"
              />
              State Government
            </label>
            <label className={`rounded-lg border p-2 text-sm cursor-pointer ${role === "admin" ? "border-emerald-400 text-emerald-300" : "border-slate-600 text-slate-200"}`}>
              <input
                type="radio"
                name="role"
                value="admin"
                checked={role === "admin"}
                onChange={(event) => setRole(event.target.value)}
                className="mr-2"
              />
              Central Government
            </label>
          </div>
        </fieldset>

        {role === "state" ? (
          <>
            <label className="block mt-4 text-sm text-slate-300">State / UT</label>
            <select
              className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
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

        {error ? <p className="mt-4 text-sm text-red-400">{error}</p> : null}

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 w-full bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2 disabled:opacity-60"
        >
          {submitting ? "Saving profile..." : "Continue"}
        </button>
      </form>
    </main>
  );
}
