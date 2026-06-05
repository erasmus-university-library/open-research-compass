import Link from "next/link";

const capabilities = [
  { icon: "👤", label: "Find experts", description: "Identify leading researchers by field or topic" },
  { icon: "📄", label: "Explore topics", description: "Search concepts, methods, and research themes" },
  { icon: "📊", label: "Run statistics", description: "Query publication trends and dataset metrics" },
  { icon: "🔗", label: "Find similar work", description: "Discover publications related to a given paper" },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-white px-6">
      <main className="flex w-full max-w-2xl flex-col items-center gap-10 text-center">
        <div className="flex flex-col gap-4">
          <h1 className="text-4xl font-semibold tracking-tight text-[#002328]">
            Open Research Compass
          </h1>
          <p className="text-lg leading-7 text-[#002328]/70">
            An AI agent that interacts with the Erasmus University publication database.
            Ask natural language questions to explore research, find experts, and analyse trends.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 w-full">
          {capabilities.map(({ icon, label, description }) => (
            <div
              key={label}
              className="flex flex-col gap-1 rounded-[0.4rem] border border-[#e3dad8] bg-white px-4 py-3 text-left"
            >
              <span className="text-xl">{icon}</span>
              <span className="font-medium text-[#002328] text-sm">{label}</span>
              <span className="text-xs text-[#002328]/60">{description}</span>
            </div>
          ))}
        </div>

        <Link
          href="/app/default"
          className="inline-flex h-11 items-center justify-center rounded-[1.2rem] bg-[#0c8066] px-8 text-sm font-medium text-white transition-colors hover:bg-[#002328]"
        >
          Start exploring →
        </Link>
      </main>
    </div>
  );
}
