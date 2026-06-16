import React, { useState, useEffect, useRef } from "react";
import {
  Plus, X, Image as ImageIcon, Video, Check, ArrowRight, ChevronDown,
  ExternalLink, RotateCcw, Link2, BarChart3, Send, Eye, MessageCircle,
  Info, Loader2, LogOut, DoorOpen,
} from "lucide-react";

/* ──────────────────────────────────────────────
   СТОРИСКАСТ — прототип сервиса рассылки сторис
   Дизайн: диспетчерская. Mono несёт "пультовую"
   личность, линия маршрута + янтарный сигнал — фирменный.
   Экраны: Создать · Каналы · Аналитика.
   ────────────────────────────────────────────── */

const T = {
  canvas: "#E9E7E0", ink: "#16181D", sub: "#6B7078",
  line: "#D7D3CA", surface: "#FFFFFF", primary: "#1B3A8F",
  live: "#EC8B2B", ok: "#2F9E44",
};
const SANS = "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
const MONO = "ui-monospace, SFMono-Regular, Menlo, 'Roboto Mono', monospace";

const PLATFORMS = [
  { id: "vk", name: "ВКонтакте", color: "#0077FF", mode: "direct", note: "Прямая публикация" },
  { id: "tg", name: "Telegram", color: "#29A9EB", mode: "direct", note: "Личный профиль · лимит 3/день" },
  { id: "ig", name: "Instagram", color: "#E1306C", mode: "direct", note: "Graph API" },
  { id: "fb", name: "Facebook", color: "#1877F2", mode: "auto", note: "Прицепом через Instagram" },
  { id: "wa", name: "WhatsApp Status", color: "#25D366", mode: "manual", note: "Личный профиль · вручную" },
];

const ACCOUNTS = [
  { id: "me", label: "Ilfat Sistema", kind: "Мой профиль" },
  { id: "c1", label: "Кафе «Огонь»", kind: "Клиент" },
  { id: "c2", label: "Студия Ирины", kind: "Клиент" },
];

// стартовые состояния подключений
const INIT_CONN = {
  vk: { state: "on", handle: "@ilfat_sistema", sub: "3 420 подписчиков" },
  tg: { state: "on", handle: "+7 917 •• •• 04", sub: "личный профиль" },
  ig: { state: "on", handle: "@ilfaaat_sistem", sub: "8 140 подписчиков" },
  fb: { state: "auto", handle: "Ilfat Sistema", sub: "через Instagram" },
  wa: { state: "manual", handle: "личный номер", sub: "Status · 24 ч" },
};

// мок-аналитика последней сторис
const LAST = {
  when: "сегодня, 20:45", files: 2,
  rows: [
    { id: "vk", reach: 1240, extra: "312 зрителей в списке" },
    { id: "ig", reach: 980, extra: "показы 1530 · ответы 12 · выходы 40" },
    { id: "fb", reach: 470, extra: "прицепом из Instagram" },
    { id: "tg", reach: 410, extra: "просмотры" },
  ],
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const P = (id) => PLATFORMS.find((p) => p.id === id);

export default function App() {
  const [tab, setTab] = useState("create"); // create | channels | analytics
  const [screen, setScreen] = useState("compose"); // compose | publishing | done
  const [media, setMedia] = useState([]);
  const [caption, setCaption] = useState("");
  const [sel, setSel] = useState({ vk: true, tg: true, ig: true, wa: false });
  const [acct, setAcct] = useState(0);
  const [acctOpen, setAcctOpen] = useState(false);
  const [status, setStatus] = useState({});
  const [conn, setConn] = useState(INIT_CONN);
  const cancelled = useRef(false);

  const fbOn = sel.ig;
  const addMedia = (type) => {
    if (media.length >= 6) return;
    const hue = [16, 200, 280, 140, 340, 40][media.length % 6];
    setMedia((m) => [...m, { id: Date.now() + Math.random(), type, hue }]);
  };
  const removeMedia = (id) => setMedia((m) => m.filter((x) => x.id !== id));

  const activeTargets = PLATFORMS.filter((p) => (p.id === "fb" ? fbOn : sel[p.id]));
  const canPublish = media.length > 0 && (sel.vk || sel.tg || sel.ig || sel.wa);

  const reset = () => {
    cancelled.current = true;
    setScreen("compose"); setMedia([]); setCaption(""); setStatus({});
  };

  const connect = async (id) => {
    setConn((c) => ({ ...c, [id]: { ...c[id], state: "connecting" } }));
    await sleep(1200);
    setConn((c) => ({ ...c, [id]: { ...c[id], state: "on" } }));
  };

  useEffect(() => {
    if (screen !== "publishing") return;
    cancelled.current = false;
    const run = async () => {
      const order = [];
      if (sel.vk) order.push("vk");
      if (sel.tg) order.push("tg");
      if (sel.ig) order.push("ig");
      if (fbOn) order.push("fb");
      const init = {};
      order.forEach((id) => (init[id] = "queued"));
      if (sel.wa) init.wa = "manual";
      setStatus(init);
      await sleep(500);
      for (const id of order) {
        if (cancelled.current) return;
        setStatus((s) => ({ ...s, [id]: "sending" }));
        await sleep(id === "fb" ? 1300 : 950);
        if (cancelled.current) return;
        setStatus((s) => ({ ...s, [id]: "done" }));
        await sleep(280);
      }
      await sleep(450);
      if (!cancelled.current) setScreen("done");
    };
    run();
    return () => { cancelled.current = true; };
  }, [screen]);

  const showActionFooter = tab === "create";

  return (
    <div style={{ background: "#cfccc3", fontFamily: SANS, minHeight: "100vh" }} className="w-full flex items-center justify-center p-4">
      <style>{`
        @keyframes sig {0%{transform:scale(1);opacity:.55}70%{transform:scale(2.4);opacity:0}100%{opacity:0}}
        @media (prefers-reduced-motion: reduce){.sig{animation:none!important}.spin{animation:none!important}}
        .scl::-webkit-scrollbar{display:none}
        .spin{animation:spin 1s linear infinite}
        @keyframes spin{to{transform:rotate(360deg)}}
      `}</style>

      <div style={{ background: "#0e0f12", borderRadius: 44, padding: 11, boxShadow: "0 30px 70px -20px rgba(0,0,0,.55)" }} className="w-full">
        <div style={{ maxWidth: 392, margin: "0 auto" }}>
          <div style={{ background: T.canvas, borderRadius: 34, height: 780 }} className="overflow-hidden flex flex-col relative">

            {/* status bar */}
            <div style={{ color: T.ink }} className="flex justify-between items-center px-6 pt-3 pb-1 text-[12px] font-semibold">
              <span style={{ fontFamily: MONO }}>20:45</span>
              <span style={{ fontFamily: MONO, letterSpacing: 1 }} className="opacity-60">●●●  ◔</span>
            </div>

            {/* top bar */}
            <div className="px-5 pt-1 pb-3 flex items-center justify-between relative">
              <div className="flex items-center gap-2">
                <div style={{ background: T.ink, color: T.canvas, fontFamily: MONO }} className="w-7 h-7 rounded-lg flex items-center justify-center text-[15px] font-bold">⌁</div>
                <div className="leading-none">
                  <div style={{ color: T.ink, letterSpacing: 0.5 }} className="text-[15px] font-extrabold">СТОРИСКАСТ</div>
                  <div style={{ color: T.sub, fontFamily: MONO }} className="text-[9px] tracking-wider uppercase mt-[3px]">одна загрузка · все каналы</div>
                </div>
              </div>
              <button onClick={() => setAcctOpen((v) => !v)} style={{ background: T.surface, border: `1px solid ${T.line}`, color: T.ink }} className="flex items-center gap-1.5 rounded-full pl-1.5 pr-2 py-1">
                <span style={{ background: T.primary }} className="w-5 h-5 rounded-full text-white text-[10px] font-bold flex items-center justify-center">{ACCOUNTS[acct].label[0]}</span>
                <span className="text-[11px] font-semibold max-w-[68px] truncate">{ACCOUNTS[acct].label}</span>
                <ChevronDown size={13} style={{ color: T.sub }} />
              </button>
              {acctOpen && (
                <div style={{ background: T.surface, border: `1px solid ${T.line}`, boxShadow: "0 12px 30px -10px rgba(0,0,0,.25)" }} className="absolute right-5 top-[52px] rounded-2xl p-1.5 w-[210px] z-30">
                  <div style={{ color: T.sub, fontFamily: MONO }} className="text-[9px] uppercase tracking-wider px-2 py-1">Профиль публикации</div>
                  {ACCOUNTS.map((a, i) => (
                    <button key={a.id} onClick={() => { setAcct(i); setAcctOpen(false); }} style={{ background: i === acct ? T.canvas : "transparent" }} className="w-full flex items-center gap-2 rounded-xl px-2 py-2 text-left">
                      <span style={{ background: i === acct ? T.primary : T.sub }} className="w-6 h-6 rounded-full text-white text-[11px] font-bold flex items-center justify-center">{a.label[0]}</span>
                      <span className="leading-tight">
                        <span style={{ color: T.ink }} className="block text-[12.5px] font-semibold">{a.label}</span>
                        <span style={{ color: T.sub }} className="block text-[10px]">{a.kind}</span>
                      </span>
                      {i === acct && <Check size={15} style={{ color: T.primary, marginLeft: "auto" }} />}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* body */}
            <div onClick={() => acctOpen && setAcctOpen(false)} className="flex-1 overflow-y-auto scl px-5 pb-3">
              {tab === "create" && screen === "compose" && (
                <Compose media={media} addMedia={addMedia} removeMedia={removeMedia} caption={caption} setCaption={setCaption} sel={sel} setSel={setSel} fbOn={fbOn} />
              )}
              {tab === "create" && screen === "publishing" && (
                <Publishing targets={activeTargets} status={status} setStatus={setStatus} media={media} />
              )}
              {tab === "create" && screen === "done" && (
                <Done targets={activeTargets} status={status} goAnalytics={() => setTab("analytics")} />
              )}
              {tab === "channels" && <Channels conn={conn} connect={connect} />}
              {tab === "analytics" && <Analytics />}
            </div>

            {/* contextual footer */}
            {showActionFooter && (
              <div style={{ borderTop: `1px solid ${T.line}`, background: T.canvas }} className="px-5 py-3">
                {screen === "compose" && (
                  <button disabled={!canPublish} onClick={() => setScreen("publishing")} style={{ background: canPublish ? T.primary : "#c9c6bd", color: canPublish ? "#fff" : "#8d8a82" }} className="w-full rounded-2xl py-3.5 font-bold text-[15px] flex items-center justify-center gap-2 transition-colors">
                    Опубликовать везде <ArrowRight size={18} />
                  </button>
                )}
                {screen === "publishing" && (
                  <div style={{ color: T.sub }} className="text-[11.5px] text-center flex items-center justify-center gap-2 py-1">
                    <span style={{ background: T.live }} className="w-2 h-2 rounded-full" />
                    Публикуем на сервере — приложение можно закрыть
                  </div>
                )}
                {screen === "done" && (
                  <button onClick={reset} style={{ background: T.ink, color: T.canvas }} className="w-full rounded-2xl py-3.5 font-bold text-[15px] flex items-center justify-center gap-2">
                    <RotateCcw size={17} /> Новая сторис
                  </button>
                )}
              </div>
            )}

            {/* tab bar */}
            <div style={{ borderTop: `1px solid ${T.line}`, background: T.surface }} className="flex">
              {[
                { id: "create", label: "Создать", icon: Send },
                { id: "channels", label: "Каналы", icon: Link2 },
                { id: "analytics", label: "Аналитика", icon: BarChart3 },
              ].map((t) => {
                const on = tab === t.id;
                const Icon = t.icon;
                return (
                  <button key={t.id} onClick={() => { setTab(t.id); }} className="flex-1 flex flex-col items-center gap-1 py-2.5">
                    <Icon size={20} style={{ color: on ? T.primary : T.sub }} strokeWidth={on ? 2.4 : 1.8} />
                    <span style={{ color: on ? T.ink : T.sub }} className="text-[10px] font-semibold">{t.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── COMPOSE ───────────────────────────── */
function Compose({ media, addMedia, removeMedia, caption, setCaption, sel, setSel, fbOn }) {
  return (
    <div className="pt-1">
      <SectionLabel n="01" title="Что публикуем" />
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 20 }} className="p-3 mb-2">
        {media.length === 0 ? (
          <div className="flex gap-2">
            <AddTile icon={<ImageIcon size={20} />} label="Фото" onClick={() => addMedia("photo")} />
            <AddTile icon={<Video size={20} />} label="Видео" onClick={() => addMedia("video")} />
          </div>
        ) : (
          <div className="flex gap-2 overflow-x-auto scl">
            {media.map((m, i) => (
              <div key={m.id} className="relative shrink-0">
                <div style={{ width: 70, height: 96, borderRadius: 12, background: `linear-gradient(150deg, hsl(${m.hue} 70% 62%), hsl(${(m.hue + 40) % 360} 65% 45%))` }} className="flex items-end p-1.5">
                  <span style={{ fontFamily: MONO }} className="text-white/90 text-[9px] font-bold flex items-center gap-0.5">
                    {m.type === "video" ? <Video size={11} /> : <ImageIcon size={11} />}{i + 1}
                  </span>
                </div>
                <button onClick={() => removeMedia(m.id)} style={{ background: T.ink }} className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full text-white flex items-center justify-center"><X size={12} /></button>
              </div>
            ))}
            {media.length < 6 && (
              <button onClick={() => addMedia("photo")} style={{ width: 70, height: 96, border: `1.5px dashed ${T.line}`, color: T.sub, borderRadius: 12 }} className="shrink-0 flex flex-col items-center justify-center gap-1">
                <Plus size={18} /><span className="text-[10px] font-semibold">Ещё</span>
              </button>
            )}
          </div>
        )}
        <input value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Подпись (необязательно)…" style={{ color: T.ink, borderTop: media.length ? `1px solid ${T.line}` : "none" }} className="w-full bg-transparent outline-none text-[13.5px] mt-3 pt-3 placeholder:text-stone-400" />
      </div>

      <div className="mt-5"><SectionLabel n="02" title="Куда уходит" /></div>
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 20 }} className="px-3 py-1.5 mb-1 relative">
        <div style={{ position: "absolute", left: 22, top: 26, bottom: 26, width: 2, background: T.line }} />
        {PLATFORMS.map((p) => {
          const on = p.id === "fb" ? fbOn : !!sel[p.id];
          const nested = p.id === "fb";
          return <DestRow key={p.id} p={p} on={on} nested={nested} locked={p.id === "fb"} onToggle={() => p.id !== "fb" && setSel((s) => ({ ...s, [p.id]: !s[p.id] }))} />;
        })}
      </div>
      <p style={{ color: T.sub }} className="text-[11px] leading-snug px-1 mt-2">
        Facebook подтянется автоматически вслед за Instagram. WhatsApp Status — ваш личный профиль, ставится вручную в один тап.
      </p>
    </div>
  );
}

function DestRow({ p, on, nested, locked, onToggle }) {
  return (
    <div className="flex items-center gap-3 py-2.5 relative" style={{ paddingLeft: nested ? 22 : 0 }}>
      {nested && <div style={{ position: "absolute", left: 22, top: -2, width: 18, height: 22, borderLeft: `2px solid ${T.line}`, borderBottom: `2px solid ${T.line}`, borderBottomLeftRadius: 8 }} />}
      <span style={{ background: on ? p.color : "#cfccc3", outline: `4px solid ${T.surface}` }} className="w-3.5 h-3.5 rounded-full shrink-0 z-10" />
      <div className="flex-1 leading-tight">
        <div style={{ color: on ? T.ink : T.sub }} className="text-[14px] font-semibold flex items-center gap-1.5">
          {p.name}
          {p.mode === "auto" && <Tag>авто</Tag>}
          {p.mode === "manual" && <Tag>вручную</Tag>}
        </div>
        <div style={{ color: T.sub }} className="text-[10.5px] mt-0.5">{p.note}</div>
      </div>
      <button onClick={onToggle} disabled={locked} style={{ background: on ? p.color : "#cdc9c0", opacity: locked ? 0.5 : 1 }} className="w-[42px] h-[24px] rounded-full relative shrink-0 transition-colors" aria-label={`${p.name} ${on ? "включён" : "выключен"}`}>
        <span style={{ left: on ? 20 : 2 }} className="absolute top-[2px] w-5 h-5 rounded-full bg-white transition-all" />
      </button>
    </div>
  );
}

/* ── PUBLISHING ────────────────────────── */
function Publishing({ targets, status, setStatus, media }) {
  return (
    <div className="pt-2">
      <div className="flex items-center justify-between mb-1">
        <SectionLabel n="→" title="Рассылка" />
        <span style={{ color: T.sub, fontFamily: MONO }} className="text-[10px]">{Object.values(status).filter((s) => s === "done").length}/{targets.length}</span>
      </div>
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 18 }} className="flex items-center gap-3 p-2.5 mb-3">
        <div style={{ width: 38, height: 50, borderRadius: 8, background: `linear-gradient(150deg, hsl(${media[0]?.hue ?? 16} 70% 62%), hsl(${((media[0]?.hue ?? 16) + 40) % 360} 65% 45%))` }} />
        <div className="leading-tight">
          <div style={{ color: T.ink }} className="text-[13px] font-bold">{media.length} {media.length === 1 ? "файл" : "файла"} в рассылке</div>
          <div style={{ color: T.sub, fontFamily: MONO }} className="text-[10px] mt-0.5">id cast_8f2a · {new Date().toLocaleDateString("ru-RU")}</div>
        </div>
      </div>
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 20 }} className="px-3.5 py-1.5 relative">
        <div style={{ position: "absolute", left: 23, top: 28, bottom: 28, width: 2, background: T.line }} />
        {targets.map((p) => <DispatchRow key={p.id} p={p} st={status[p.id]} onManual={() => setStatus((s) => ({ ...s, [p.id]: "done" }))} />)}
      </div>
    </div>
  );
}

function DispatchRow({ p, st, onManual }) {
  const c = st === "done" ? T.ok : st === "sending" ? T.live : st === "manual" ? p.color : T.sub;
  return (
    <div className="flex items-center gap-3 py-3 relative" style={{ paddingLeft: p.id === "fb" ? 22 : 0 }}>
      {p.id === "fb" && <div style={{ position: "absolute", left: 23, top: -4, width: 18, height: 26, borderLeft: `2px solid ${T.line}`, borderBottom: `2px solid ${T.line}`, borderBottomLeftRadius: 8 }} />}
      <span className="relative w-4 h-4 shrink-0 z-10" style={{ outline: `4px solid ${T.surface}`, borderRadius: 99 }}>
        <span style={{ background: c }} className="absolute inset-0 rounded-full" />
        {st === "sending" && <span className="sig absolute inset-0 rounded-full" style={{ background: T.live, animation: "sig 1s ease-out infinite" }} />}
        {st === "done" && <Check size={11} className="absolute inset-0 m-auto text-white" />}
      </span>
      <div className="flex-1 leading-tight">
        <div style={{ color: T.ink }} className="text-[14px] font-semibold">{p.name}</div>
        <div style={{ color: T.sub, fontFamily: MONO }} className="text-[10px] uppercase tracking-wide mt-0.5">
          {st === "queued" && "в очереди"}{st === "sending" && "отправка…"}{st === "done" && "опубликовано"}{st === "manual" && "ваш ход"}
        </div>
      </div>
      {st === "manual" && (
        <button onClick={onManual} style={{ background: p.color }} className="text-white text-[11px] font-bold rounded-full px-3 py-1.5 flex items-center gap-1">Открыть <ExternalLink size={12} /></button>
      )}
    </div>
  );
}

/* ── DONE ──────────────────────────────── */
function Done({ targets, status, goAnalytics }) {
  const done = targets.filter((p) => status[p.id] === "done").length;
  const pending = targets.filter((p) => status[p.id] === "manual");
  return (
    <div className="pt-4 flex flex-col items-center text-center">
      <div style={{ background: T.ok }} className="w-16 h-16 rounded-full flex items-center justify-center mb-4"><Check size={32} className="text-white" /></div>
      <div style={{ color: T.ink }} className="text-[22px] font-extrabold leading-tight">Разослано</div>
      <div style={{ color: T.sub }} className="text-[13px] mt-1 mb-5">{done} из {targets.length} каналов · {new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</div>
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 18 }} className="w-full px-3 py-1 mb-3">
        {targets.map((p) => (
          <div key={p.id} style={{ borderBottom: `1px solid ${T.line}` }} className="flex items-center gap-2.5 py-2.5 last:border-0">
            <span style={{ background: p.color }} className="w-3 h-3 rounded-full" />
            <span style={{ color: T.ink }} className="text-[13.5px] font-semibold flex-1 text-left">{p.name}</span>
            {status[p.id] === "done"
              ? <span style={{ color: T.ok, fontFamily: MONO }} className="text-[10.5px] uppercase flex items-center gap-1"><Check size={13} /> готово</span>
              : <span style={{ color: T.live, fontFamily: MONO }} className="text-[10.5px] uppercase">ожидает</span>}
          </div>
        ))}
      </div>
      {pending.length > 0 && <p style={{ color: T.sub }} className="text-[11.5px] leading-snug px-2 mb-3">WhatsApp Status ждёт вашего тапа — остальное уже в мире.</p>}
      <button onClick={goAnalytics} style={{ color: T.primary }} className="text-[12.5px] font-bold flex items-center gap-1.5"><BarChart3 size={15} /> Посмотреть, как разошлось</button>
    </div>
  );
}

/* ── CHANNELS (онбординг/подключения) ──── */
function Channels({ conn, connect }) {
  return (
    <div className="pt-1">
      <SectionLabel n="✦" title="Подключённые каналы" />
      <div className="flex flex-col gap-2 mb-4">
        {PLATFORMS.map((p) => {
          const c = conn[p.id];
          return (
            <div key={p.id} style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 16 }} className="flex items-center gap-3 p-3">
              <span style={{ background: p.color }} className="w-9 h-9 rounded-full flex items-center justify-center text-white text-[13px] font-bold shrink-0">{p.name[0]}</span>
              <div className="flex-1 leading-tight min-w-0">
                <div style={{ color: T.ink }} className="text-[13.5px] font-semibold flex items-center gap-1.5">
                  {p.name}
                  {c.state === "auto" && <Tag>авто</Tag>}
                  {c.state === "manual" && <Tag>вручную</Tag>}
                </div>
                <div style={{ color: T.sub, fontFamily: MONO }} className="text-[10.5px] mt-0.5 truncate">
                  {c.state === "off" ? "не подключён" : `${c.handle} · ${c.sub}`}
                </div>
              </div>
              {c.state === "on" && <span style={{ color: T.ok, fontFamily: MONO }} className="text-[10px] uppercase flex items-center gap-1 shrink-0"><Check size={13} /> подключён</span>}
              {c.state === "auto" && <span style={{ color: T.sub, fontFamily: MONO }} className="text-[10px] uppercase shrink-0">прицепом</span>}
              {c.state === "manual" && <span style={{ color: p.color, fontFamily: MONO }} className="text-[10px] uppercase shrink-0">в 1 тап</span>}
              {c.state === "connecting" && <Loader2 size={16} className="spin shrink-0" style={{ color: T.primary }} />}
              {c.state === "off" && (
                <button onClick={() => connect(p.id)} style={{ background: T.primary }} className="text-white text-[11.5px] font-bold rounded-full px-3 py-1.5 shrink-0">Подключить</button>
              )}
            </div>
          );
        })}
      </div>

      {/* пояснение про WhatsApp — Status vs Каналы */}
      <div style={{ background: "#fff7ed", border: `1px solid #f3d9b8`, borderRadius: 16 }} className="p-3 flex gap-2.5">
        <Info size={16} style={{ color: T.live }} className="shrink-0 mt-0.5" />
        <div style={{ color: "#7a5320" }} className="text-[11.5px] leading-snug">
          <b>WhatsApp Status</b> — это истории на вашем <b>личном профиле</b> (живут 24 ч). Это не «WhatsApp Каналы» — лента для подписчиков, к сторис она отношения не имеет. Официального API для Status нет, поэтому сервис открывает готовую историю, а вы публикуете её в один тап.
        </div>
      </div>

      {/* пояснение про Telegram-вход */}
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 16 }} className="p-3 flex gap-2.5 mt-2">
        <DoorOpen size={16} style={{ color: T.primary }} className="shrink-0 mt-0.5" />
        <div style={{ color: T.sub }} className="text-[11.5px] leading-snug">
          <b style={{ color: T.ink }}>Telegram</b> подключается по номеру и коду из приложения (личный профиль). Лимит без Premium — 3 истории в сутки; сервис ставит лишнее в очередь.
        </div>
      </div>
    </div>
  );
}

/* ── ANALYTICS ─────────────────────────── */
function Analytics() {
  const total = LAST.rows.reduce((a, r) => a + r.reach, 0);
  const max = Math.max(...LAST.rows.map((r) => r.reach));
  return (
    <div className="pt-1">
      <SectionLabel n="∑" title="Как разошлась сторис" />
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 18 }} className="flex items-center gap-3 p-3 mb-3">
        <div style={{ width: 40, height: 54, borderRadius: 8, background: "linear-gradient(150deg, hsl(16 70% 62%), hsl(56 65% 45%))" }} />
        <div className="leading-tight">
          <div style={{ color: T.ink }} className="text-[13px] font-bold">Шашлык у мангала</div>
          <div style={{ color: T.sub, fontFamily: MONO }} className="text-[10px] mt-0.5">{LAST.files} файла · {LAST.when}</div>
        </div>
      </div>

      {/* суммарный охват */}
      <div style={{ background: T.ink, borderRadius: 18 }} className="p-4 mb-3">
        <div style={{ color: "#b9bcc4", fontFamily: MONO }} className="text-[10px] uppercase tracking-widest">суммарный охват</div>
        <div className="flex items-baseline gap-2 mt-1">
          <span style={{ color: T.canvas }} className="text-[34px] font-extrabold leading-none">{total.toLocaleString("ru-RU")}</span>
          <span style={{ color: T.live, fontFamily: MONO }} className="text-[12px] font-bold">по 4 каналам</span>
        </div>
      </div>

      {/* разбивка по каналам */}
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 18 }} className="px-3.5 py-2 mb-3">
        {LAST.rows.map((r) => {
          const p = P(r.id);
          return (
            <div key={r.id} style={{ borderBottom: `1px solid ${T.line}` }} className="py-3 last:border-0">
              <div className="flex items-center gap-2 mb-1.5">
                <span style={{ background: p.color }} className="w-3 h-3 rounded-full" />
                <span style={{ color: T.ink }} className="text-[13px] font-semibold flex-1">{p.name}</span>
                <span style={{ color: T.ink, fontFamily: MONO }} className="text-[13px] font-bold">{r.reach.toLocaleString("ru-RU")}</span>
              </div>
              <div style={{ background: "#ece9e2", borderRadius: 99, height: 6 }} className="w-full overflow-hidden">
                <div style={{ width: `${(r.reach / max) * 100}%`, background: p.color, height: "100%", borderRadius: 99 }} />
              </div>
              <div style={{ color: T.sub }} className="text-[10.5px] mt-1.5 flex items-center gap-1.5">
                {r.id === "vk" && <Eye size={12} />}{r.id === "ig" && <MessageCircle size={12} />}
                {r.extra}
              </div>
            </div>
          );
        })}
      </div>

      <p style={{ color: T.sub }} className="text-[11px] leading-snug px-1">
        Статистика Instagram собирается автоматически в течение суток — до того, как история истечёт. VK отдаёт поимённый список зрителей.
      </p>
    </div>
  );
}

/* ── bits ──────────────────────────────── */
function SectionLabel({ n, title }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <span style={{ color: T.live, fontFamily: MONO }} className="text-[12px] font-bold">{n}</span>
      <span style={{ color: T.ink, letterSpacing: 0.3 }} className="text-[12px] font-bold uppercase tracking-wide">{title}</span>
    </div>
  );
}
function Tag({ children }) {
  return <span style={{ background: T.canvas, color: T.sub, fontFamily: MONO }} className="text-[8.5px] uppercase tracking-wide px-1.5 py-0.5 rounded font-bold">{children}</span>;
}
function AddTile({ icon, label, onClick }) {
  return (
    <button onClick={onClick} style={{ border: `1.5px dashed ${T.line}`, color: T.sub, borderRadius: 14 }} className="flex-1 h-[96px] flex flex-col items-center justify-center gap-1.5">
      {icon}<span className="text-[12px] font-semibold">{label}</span>
    </button>
  );
}
