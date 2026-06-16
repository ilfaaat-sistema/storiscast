import { T, MONO } from "../tokens.js";

export function SectionLabel({ n, title }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <span style={{ color: T.live, fontFamily: MONO }} className="text-[12px] font-bold">{n}</span>
      <span style={{ color: T.ink, letterSpacing: 0.3 }} className="text-[12px] font-bold uppercase tracking-wide">{title}</span>
    </div>
  );
}

export function Tag({ children }) {
  return (
    <span style={{ background: T.canvas, color: T.sub, fontFamily: MONO }}
      className="text-[8.5px] uppercase tracking-wide px-1.5 py-0.5 rounded font-bold">
      {children}
    </span>
  );
}

export function AddTile({ icon, label, onClick }) {
  return (
    <button onClick={onClick}
      style={{ border: `1.5px dashed ${T.line}`, color: T.sub, borderRadius: 14 }}
      className="flex-1 h-[96px] flex flex-col items-center justify-center gap-1.5">
      {icon}<span className="text-[12px] font-semibold">{label}</span>
    </button>
  );
}
