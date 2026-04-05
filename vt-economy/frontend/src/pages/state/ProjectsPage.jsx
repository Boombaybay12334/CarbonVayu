// PAGE: ProjectsPage
// ROUTE: /app/projects
// ROLE: state
// DATA SOURCE: projectsService (DUMMY)
// STATUS: Scaffold

import { useEffect, useState } from "react";
import { createProject, getProjects } from "../../services/projectsService";

export default function ProjectsPage() {
  const [activeTab, setActiveTab] = useState("browse");
  const [projects, setProjects] = useState([]);
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    title: "",
    description: "",
    vt_gain_estimate: "",
    funds_needed: "",
  });

  useEffect(() => {
    getProjects().then(setProjects);
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const payload = {
      ...form,
      vt_gain_estimate: Number(form.vt_gain_estimate),
      funds_needed: Number(form.funds_needed),
    };

    await createProject(payload);
    setMessage("Project submitted successfully (dummy response).");
    setForm({ title: "", description: "", vt_gain_estimate: "", funds_needed: "" });
  }

  function percentRaised(project) {
    if (!project.funds_needed) return 0;
    return Math.min(100, Math.round((project.funds_raised / project.funds_needed) * 100));
  }

  return (
    <section className="rounded-xl shadow-md p-4 bg-slate-800 border border-slate-700">
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setActiveTab("browse")}
          className={`rounded-lg px-4 py-2 ${activeTab === "browse" ? "bg-emerald-600 text-white" : "border border-slate-600 text-slate-300"}`}
        >
          Browse Projects
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("post")}
          className={`rounded-lg px-4 py-2 ${activeTab === "post" ? "bg-emerald-600 text-white" : "border border-slate-600 text-slate-300"}`}
        >
          Post a Project
        </button>
      </div>

      {activeTab === "browse" ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <article key={project.id} className="rounded-xl border border-slate-700 bg-slate-900 p-4">
              <p className="text-xs text-slate-400">{project.state_name}</p>
              <h3 className="mt-1 font-semibold">{project.title}</h3>
              <p className="mt-2 text-sm text-slate-300 line-clamp-3">{project.description}</p>
              <p className="mt-3 inline-block rounded-full bg-emerald-500/20 px-2 py-1 text-xs text-emerald-300">
                VT +{project.vt_gain_estimate}
              </p>

              <div className="mt-4">
                <div className="h-2 rounded-full bg-slate-700 overflow-hidden">
                  <div className="h-full bg-emerald-500" style={{ width: `${percentRaised(project)}%` }} />
                </div>
                <p className="mt-2 text-xs text-slate-400">{percentRaised(project)}% funded</p>
              </div>

              <button
                type="button"
                onClick={() => setMessage(`DUMMY: Invest action for ${project.title}`)}
                className="mt-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2"
              >
                Invest
              </button>
            </article>
          ))}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-4 max-w-2xl space-y-3">
          <input
            type="text"
            placeholder="Project title"
            className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2"
            value={form.title}
            onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
            required
          />
          <textarea
            placeholder="Description"
            className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 min-h-[120px]"
            value={form.description}
            onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
            required
          />
          <input
            type="number"
            placeholder="VT goal"
            className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2"
            value={form.vt_gain_estimate}
            onChange={(event) => setForm((prev) => ({ ...prev, vt_gain_estimate: event.target.value }))}
            required
          />
          <input
            type="number"
            placeholder="Funds needed"
            className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2"
            value={form.funds_needed}
            onChange={(event) => setForm((prev) => ({ ...prev, funds_needed: event.target.value }))}
            required
          />

          <button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2">
            Submit Project
          </button>
        </form>
      )}

      {message ? <p className="mt-4 text-sm text-emerald-300">{message}</p> : null}
    </section>
  );
}
