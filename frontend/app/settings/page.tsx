export default function SettingsPage() {
  return (
    <section className="space-y-6">
      <div className="card">
        <h1 className="mb-3 text-3xl font-semibold">Search preferences</h1>
        <p className="text-white/70">
          Wire this page to the <code>/preferences</code> API endpoint to save origin airports,
          destination modes, cabin class, and thresholds.
        </p>
      </div>

      <form className="card grid gap-4">
        <label className="grid gap-2">
          <span>Origin airports</span>
          <input className="rounded-xl border border-white/10 bg-black/20 px-4 py-3" placeholder="SLC,LAX,DEN" />
        </label>

        <label className="grid gap-2">
          <span>Destination mode</span>
          <select className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
            <option>anywhere</option>
            <option>region</option>
            <option>city</option>
          </select>
        </label>

        <label className="grid gap-2">
          <span>Max price</span>
          <input type="number" className="rounded-xl border border-white/10 bg-black/20 px-4 py-3" placeholder="500" />
        </label>

        <button type="button" className="rounded-xl bg-white px-4 py-3 font-medium text-slate-900">
          Save preference
        </button>
      </form>
    </section>
  );
}
