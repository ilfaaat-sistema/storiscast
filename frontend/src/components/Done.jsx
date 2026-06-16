import React from "react";
import { Check, RotateCcw, BarChart3 } from "lucide-react";
import { T, MONO, P } from "../tokens.js";

export default function Done({ jobs, onReset, onGoAnalytics }) {
  const done = jobs.filter((j) => j.status === "done").length;
  const pending = jobs.filter((j) => j.status === "manual");

  return (
    <div className="pt-4 flex flex-col items-center text-center">
      <div style={{ background: T.ok }} className="w-16 h-16 rounded-full flex items-center justify-center mb-4">
        <Check size={32} className="text-white" />
      </div>
      <div style={{ color: T.ink }} className="text-[22px] font-extrabold leading-tight">Разослано</div>
      <div style={{ color: T.sub }} className="text-[13px] mt-1 mb-5">
        {done} из {jobs.length} каналов · {new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
      </div>

      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 18 }}
        className="w-full px-3 py-1 mb-3">
        {jobs.map((j) => {
          const p = P(j.platform);
          if (!p) return null;
          return (
            <div key={j.id} style={{ borderBottom: `1px solid ${T.line}` }}
              className="flex items-center gap-2.5 py-2.5 last:border-0">
              <span style={{ background: p.color }} className="w-3 h-3 rounded-full" />
              <span style={{ color: T.ink }} className="text-[13.5px] font-semibold flex-1 text-left">{p.name}</span>
              {j.status === "done"
                ? <span style={{ color: T.ok, fontFamily: MONO }} className="text-[10.5px] uppercase flex items-center gap-1"><Check size={13} /> готово</span>
                : j.status === "manual"
                  ? <span style={{ color: T.live, fontFamily: MONO }} className="text-[10.5px] uppercase">ожидает</span>
                  : <span style={{ color: T.sub, fontFamily: MONO }} className="text-[10.5px] uppercase">{j.status}</span>
              }
            </div>
          );
        })}
      </div>

      {pending.length > 0 && (
        <p style={{ color: T.sub }} className="text-[11.5px] leading-snug px-2 mb-3">
          WhatsApp Status ждёт вашего тапа — остальное уже в мире.
        </p>
      )}

      <button onClick={onGoAnalytics} style={{ color: T.primary }}
        className="text-[12.5px] font-bold flex items-center gap-1.5 mb-4">
        <BarChart3 size={15} /> Посмотреть, как разошлось
      </button>
    </div>
  );
}
