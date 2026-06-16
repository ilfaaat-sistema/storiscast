import React, { useEffect, useState } from "react";
import { Eye, MessageCircle, RefreshCw } from "lucide-react";
import { T, MONO, P } from "../tokens.js";
import { SectionLabel } from "./Bits.jsx";
import { getCasts, getCastInsights } from "../api.js";

const REACH_KEYS = ["reach", "impressions", "views", "views_count"];

const METRIC_LABEL = {
  replies:         "ответы",
  likes:           "лайки",
  shares:          "репосты",
  reactions_count: "реакции",
  forwards_count:  "репосты",
  taps_forward:    "вперёд",
  taps_back:       "назад",
  exits:           "выходы",
  swipe_forward:   "смахнули",
  subscribers:     "подписки",
  open_link:       "по ссылке",
  answer:          "ответы",
  bans:            "отписки",
};

function getReach(metrics) {
  for (const k of REACH_KEYS) {
    if (metrics[k] != null) return metrics[k];
  }
  return 0;
}

function getExtra(metrics) {
  return Object.entries(metrics)
    .filter(([k, v]) => !REACH_KEYS.includes(k) && v > 0)
    .map(([k, v]) => `${METRIC_LABEL[k] ?? k} ${v.toLocaleString("ru-RU")}`)
    .join(" · ");
}

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function CastPicker({ casts, selectedId, onSelect }) {
  if (!casts.length) return null;
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 mb-3 scrollbar-none" style={{ scrollbarWidth: "none" }}>
      {casts.map((c) => {
        const active = c.id === selectedId;
        const platforms = [...new Set(c.platforms.filter((p) => p !== "wa"))];
        return (
          <button
            key={c.id}
            onClick={() => onSelect(c.id)}
            style={{
              background: active ? T.ink : T.surface,
              border: `1.5px solid ${active ? T.ink : T.line}`,
              borderRadius: 14,
              minWidth: 88,
              flexShrink: 0,
            }}
            className="px-2.5 py-2 text-left"
          >
            <div style={{ color: active ? T.canvas : T.sub, fontFamily: MONO }}
              className="text-[9px] uppercase tracking-wide leading-none mb-1">
              {fmtDate(c.created_at)}
            </div>
            <div className="flex gap-1 flex-wrap">
              {platforms.map((pid) => {
                const pl = P(pid);
                return pl ? (
                  <span key={pid}
                    style={{ background: pl.color, opacity: active ? 1 : 0.65 }}
                    className="w-2 h-2 rounded-full inline-block" />
                ) : null;
              })}
            </div>
            {c.caption && (
              <div style={{ color: active ? "#b9bcc4" : T.sub }}
                className="text-[9px] mt-1 leading-snug line-clamp-1 max-w-[72px]">
                {c.caption}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}

export default function Analytics({ lastCastId }) {
  const [casts, setCasts]           = useState([]);
  const [selectedId, setSelectedId] = useState(lastCastId);
  const [jobs, setJobs]             = useState([]);
  const [castsLoading, setCastsLoading] = useState(false);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState(null);

  // Load cast list on mount
  useEffect(() => {
    setCastsLoading(true);
    getCasts(5)
      .then((data) => {
        setCasts(data);
        if (!selectedId && data.length > 0) setSelectedId(data[0].id);
      })
      .catch(() => {})
      .finally(() => setCastsLoading(false));
  }, []);

  // Load insights when selected cast changes
  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    getCastInsights(selectedId)
      .then((data) => setJobs(data.jobs ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedId]);

  const rows = jobs
    .filter((j) => Object.keys(j.metrics).length > 0)
    .map((j) => ({
      id:     j.platform,
      status: j.status,
      reach:  getReach(j.metrics),
      extra:  getExtra(j.metrics),
    }));

  const total = rows.reduce((a, r) => a + r.reach, 0);
  const max   = rows.length ? Math.max(...rows.map((r) => r.reach)) : 1;

  if (!selectedId && !castsLoading) {
    return (
      <div className="pt-8 text-center">
        <div style={{ color: T.sub }} className="text-[13px]">
          Опубликуйте первую сторис — здесь появится аналитика.
        </div>
      </div>
    );
  }

  return (
    <div className="pt-1">
      <SectionLabel n="∑" title="Как разошлась сторис" />

      {castsLoading ? (
        <div style={{ color: T.sub }} className="text-[11px] text-center py-2">Загрузка истории…</div>
      ) : (
        <CastPicker casts={casts} selectedId={selectedId} onSelect={setSelectedId} />
      )}

      {loading && (
        <div style={{ color: T.sub }} className="text-[12px] text-center py-8 flex items-center justify-center gap-2">
          <RefreshCw size={13} className="animate-spin" /> Загружаем метрики…
        </div>
      )}
      {error && (
        <div style={{ color: T.sub }} className="text-[12px] text-center py-4">Ошибка: {error}</div>
      )}

      {!loading && !error && (
        <>
          <div style={{ background: T.ink, borderRadius: 18 }} className="p-4 mb-3">
            <div style={{ color: "#b9bcc4", fontFamily: MONO }} className="text-[10px] uppercase tracking-widest">суммарный охват</div>
            <div className="flex items-baseline gap-2 mt-1">
              <span style={{ color: T.canvas }} className="text-[34px] font-extrabold leading-none">
                {total.toLocaleString("ru-RU")}
              </span>
              {rows.length > 0 && (
                <span style={{ color: T.live, fontFamily: MONO }} className="text-[12px] font-bold">
                  по {rows.length} {rows.length === 1 ? "каналу" : "каналам"}
                </span>
              )}
            </div>
          </div>

          {rows.length > 0 ? (
            <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 18 }}
              className="px-3.5 py-2 mb-3">
              {rows.map((r) => {
                const p = P(r.id);
                if (!p) return null;
                return (
                  <div key={r.id} style={{ borderBottom: `1px solid ${T.line}` }} className="py-3 last:border-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span style={{ background: p.color }} className="w-3 h-3 rounded-full" />
                      <span style={{ color: T.ink }} className="text-[13px] font-semibold flex-1">{p.name}</span>
                      <span style={{ color: T.ink, fontFamily: MONO }} className="text-[13px] font-bold">
                        {r.reach.toLocaleString("ru-RU")}
                      </span>
                    </div>
                    <div style={{ background: "#ece9e2", borderRadius: 99, height: 6 }} className="w-full overflow-hidden">
                      <div style={{ width: `${max > 0 ? (r.reach / max) * 100 : 0}%`, background: p.color, height: "100%", borderRadius: 99 }} />
                    </div>
                    {r.extra && (
                      <div style={{ color: T.sub }} className="text-[10.5px] mt-1.5 flex items-center gap-1.5">
                        {r.id === "vk" && <Eye size={12} />}
                        {r.id === "ig" && <MessageCircle size={12} />}
                        {r.extra}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ color: T.sub }} className="text-[12px] text-center py-4">
              Данные ещё собираются — зайдите после первого цикла поллера.
            </div>
          )}

          <p style={{ color: T.sub }} className="text-[11px] leading-snug px-1">
            Статистика Instagram собирается автоматически в течение суток — до того, как история истечёт. VK отдаёт поимённый список зрителей.
          </p>
        </>
      )}
    </div>
  );
}
