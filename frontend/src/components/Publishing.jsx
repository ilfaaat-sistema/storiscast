import React from "react";
import { Check, ExternalLink } from "lucide-react";
import { T, MONO, P } from "../tokens.js";
import { SectionLabel } from "./Bits.jsx";

function DispatchRow({ p, st, onManual }) {
  const c = st === "done" ? T.ok : st === "sending" ? T.live : st === "manual" ? p.color : T.sub;
  return (
    <div className="flex items-center gap-3 py-3 relative" style={{ paddingLeft: p.id === "fb" ? 22 : 0 }}>
      {p.id === "fb" && (
        <div style={{
          position: "absolute", left: 23, top: -4, width: 18, height: 26,
          borderLeft: `2px solid ${T.line}`, borderBottom: `2px solid ${T.line}`, borderBottomLeftRadius: 8,
        }} />
      )}
      <span className="relative w-4 h-4 shrink-0 z-10" style={{ outline: `4px solid ${T.surface}`, borderRadius: 99 }}>
        <span style={{ background: c }} className="absolute inset-0 rounded-full" />
        {st === "sending" && <span className="sig absolute inset-0 rounded-full" style={{ background: T.live }} />}
        {st === "done"    && <Check size={11} className="absolute inset-0 m-auto text-white" />}
      </span>
      <div className="flex-1 leading-tight">
        <div style={{ color: T.ink }} className="text-[14px] font-semibold">{p.name}</div>
        <div style={{ color: T.sub, fontFamily: MONO }} className="text-[10px] uppercase tracking-wide mt-0.5">
          {st === "queued"    && "в очереди"}
          {st === "sending"   && "отправка…"}
          {st === "done"      && "опубликовано"}
          {st === "manual"    && "ваш ход"}
          {st === "error"     && "ошибка"}
          {st === "scheduled" && "запланировано"}
          {!st                && "—"}
        </div>
      </div>
      {st === "manual" && (
        <button onClick={onManual} style={{ background: p.color }}
          className="text-white text-[11px] font-bold rounded-full px-3 py-1.5 flex items-center gap-1">
          Открыть <ExternalLink size={12} />
        </button>
      )}
    </div>
  );
}

export default function Publishing({ jobs, castId, firstMedia }) {
  const done = jobs.filter((j) => j.status === "done").length;
  const hue = firstMedia?.hue ?? 16;

  return (
    <div className="pt-2">
      <div className="flex items-center justify-between mb-1">
        <SectionLabel n="→" title="Рассылка" />
        <span style={{ color: T.sub, fontFamily: MONO }} className="text-[10px]">{done}/{jobs.length}</span>
      </div>
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 18 }}
        className="flex items-center gap-3 p-2.5 mb-3">
        <div style={{
          width: 38, height: 50, borderRadius: 8,
          background: firstMedia?.preview
            ? `url(${firstMedia.preview}) center/cover`
            : `linear-gradient(150deg, hsl(${hue} 70% 62%), hsl(${(hue + 40) % 360} 65% 45%))`,
        }} />
        <div className="leading-tight">
          <div style={{ color: T.ink }} className="text-[13px] font-bold">
            {jobs.length} {jobs.length === 1 ? "канал" : jobs.length < 5 ? "канала" : "каналов"} в рассылке
          </div>
          <div style={{ color: T.sub, fontFamily: MONO }} className="text-[10px] mt-0.5">
            id {castId?.slice(0, 8)} · {new Date().toLocaleDateString("ru-RU")}
          </div>
        </div>
      </div>

      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 20 }}
        className="px-3.5 py-1.5 relative">
        <div style={{ position: "absolute", left: 23, top: 28, bottom: 28, width: 2, background: T.line }} />
        {jobs.map((j) => {
          const p = P(j.platform);
          if (!p) return null;
          return <DispatchRow key={j.id} p={p} st={j.status} onManual={() => {}} />;
        })}
      </div>
    </div>
  );
}
