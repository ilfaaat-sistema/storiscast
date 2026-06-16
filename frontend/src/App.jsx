import React, { useState, useEffect, useRef } from "react";
import { Send, Link2, BarChart3, ArrowRight, RotateCcw, ChevronDown, Check, LogOut } from "lucide-react";
import { T, MONO, SANS, PLATFORMS } from "./tokens.js";
import Compose     from "./components/Compose.jsx";
import Publishing  from "./components/Publishing.jsx";
import Done        from "./components/Done.jsx";
import Channels    from "./components/Channels.jsx";
import Analytics   from "./components/Analytics.jsx";
import Login       from "./components/Login.jsx";
import { uploadMedia, createCast, getCast } from "./api.js";
import { supabase } from "./supabase.js";

const HUE_CYCLE = [16, 200, 280, 140, 340, 40];
const POLL_MS = 2000;

function isSettled(job) {
  return ["done", "error", "manual"].includes(job.status);
}

export default function App() {
  const [session, setSession]         = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setAuthLoading(false);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });
    return () => subscription.unsubscribe();
  }, []);

  const [tab,    setTab]    = useState("create");   // create | channels | analytics
  const [screen, setScreen] = useState("compose");  // compose | publishing | done
  const [media,  setMedia]  = useState([]);          // { id, type, hue, preview?, url?, uploading }
  const [caption, setCaption] = useState("");
  const [sel, setSel] = useState({ vk: true, tg: true, ig: true, wa: false });
  const [acctOpen, setAcctOpen] = useState(false);

  // Publishing state
  const [castId, setCastId] = useState(null);
  const [jobs,   setJobs]   = useState([]);
  const [castError, setCastError] = useState(null);

  // Last completed cast for analytics
  const [lastCastId, setLastCastId] = useState(
    () => localStorage.getItem("lastCastId") ?? null
  );

  const pollRef = useRef(null);

  // Poll cast status while publishing
  useEffect(() => {
    if (screen !== "publishing" || !castId) return;

    const poll = async () => {
      try {
        const cast = await getCast(castId);
        setJobs(cast.jobs ?? []);
        if ((cast.jobs ?? []).every(isSettled)) {
          clearInterval(pollRef.current);
          setScreen("done");
        }
      } catch (e) {
        console.error("poll error", e);
      }
    };

    poll();
    pollRef.current = setInterval(poll, POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [screen, castId]);

  const fbOn = sel.ig;
  const uploadingAny = media.some((m) => m.uploading);
  const canPublish = media.length > 0 && !uploadingAny && (sel.vk || sel.tg || sel.ig || sel.wa);

  const handleAddFile = async (file, type) => {
    const id = `${Date.now()}-${Math.random()}`;
    const hue = HUE_CYCLE[media.length % HUE_CYCLE.length];
    const preview = URL.createObjectURL(file);
    setMedia((m) => [...m, { id, type, hue, preview, uploading: true }]);

    try {
      const { url, media_type } = await uploadMedia(file);
      setMedia((m) => m.map((x) => x.id === id ? { ...x, url, media_type, uploading: false } : x));
    } catch (e) {
      setMedia((m) => m.filter((x) => x.id !== id));
      console.error("upload error", e);
    }
  };

  const handleRemoveMedia = (id) => setMedia((m) => m.filter((x) => x.id !== id));

  const handlePublish = async () => {
    setCastError(null);
    const readyMedia = media.filter((m) => m.url).map((m) => ({ url: m.url, media_type: m.media_type ?? m.type }));
    if (!readyMedia.length) return;

    const targets = PLATFORMS
      .filter((p) => p.id === "fb" ? false : !!sel[p.id])
      .map((p) => p.id);

    try {
      const cast = await createCast({ caption, media: readyMedia, targets });
      setCastId(cast.id);
      setJobs(cast.jobs ?? []);
      localStorage.setItem("lastCastId", cast.id);
      setLastCastId(cast.id);
      setScreen("publishing");
    } catch (e) {
      setCastError(e.message);
    }
  };

  const handleReset = () => {
    clearInterval(pollRef.current);
    setScreen("compose");
    setMedia([]);
    setCaption("");
    setCastId(null);
    setJobs([]);
    setCastError(null);
  };

  const showFooter = tab === "create";

  // Auth gate
  if (authLoading) {
    return (
      <div style={{ background: "#cfccc3", minHeight: "100vh", fontFamily: MONO }}
        className="flex items-center justify-center">
        <span style={{ color: T.sub }} className="text-[12px] tracking-wider">Загрузка…</span>
      </div>
    );
  }
  if (!session) return <Login />;

  const userLabel = session.user?.email ?? "Аккаунт";

  return (
    <div style={{ background: "#cfccc3", fontFamily: SANS, minHeight: "100vh" }}
      className="w-full flex items-center justify-center p-4">

      <div style={{ background: "#0e0f12", borderRadius: 44, padding: 11, boxShadow: "0 30px 70px -20px rgba(0,0,0,.55)" }}
        className="w-full">
        <div style={{ maxWidth: 392, margin: "0 auto" }}>
          <div style={{ background: T.canvas, borderRadius: 34, height: 780 }}
            className="overflow-hidden flex flex-col relative">

            {/* status bar */}
            <div style={{ color: T.ink }}
              className="flex justify-between items-center px-6 pt-3 pb-1 text-[12px] font-semibold">
              <span style={{ fontFamily: MONO }}>
                {new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
              </span>
              <span style={{ fontFamily: MONO, letterSpacing: 1 }} className="opacity-60">●●●  ◔</span>
            </div>

            {/* top bar */}
            <div className="px-5 pt-1 pb-3 flex items-center justify-between relative">
              <div className="flex items-center gap-2">
                <div style={{ background: T.ink, color: T.canvas, fontFamily: MONO }}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-[15px] font-bold">⌁</div>
                <div className="leading-none">
                  <div style={{ color: T.ink, letterSpacing: 0.5 }} className="text-[15px] font-extrabold">СТОРИСКАСТ</div>
                  <div style={{ color: T.sub, fontFamily: MONO }} className="text-[9px] tracking-wider uppercase mt-[3px]">одна загрузка · все каналы</div>
                </div>
              </div>
              <button onClick={() => setAcctOpen((v) => !v)}
                style={{ background: T.surface, border: `1px solid ${T.line}`, color: T.ink }}
                className="flex items-center gap-1.5 rounded-full pl-1.5 pr-2 py-1">
                <span style={{ background: T.primary }}
                  className="w-5 h-5 rounded-full text-white text-[10px] font-bold flex items-center justify-center">
                  {userLabel[0].toUpperCase()}
                </span>
                <span className="text-[11px] font-semibold max-w-[68px] truncate">{userLabel}</span>
                <ChevronDown size={13} style={{ color: T.sub }} />
              </button>
              {acctOpen && (
                <div style={{ background: T.surface, border: `1px solid ${T.line}`, boxShadow: "0 12px 30px -10px rgba(0,0,0,.25)" }}
                  className="absolute right-5 top-[52px] rounded-2xl p-1.5 w-[210px] z-30">
                  <div style={{ color: T.sub, fontFamily: MONO }} className="text-[9px] uppercase tracking-wider px-2 py-1">Профиль</div>
                  <div style={{ background: T.canvas }}
                    className="flex items-center gap-2 rounded-xl px-2 py-2">
                    <span style={{ background: T.primary }}
                      className="w-6 h-6 rounded-full text-white text-[11px] font-bold flex items-center justify-center shrink-0">
                      {userLabel[0].toUpperCase()}
                    </span>
                    <span className="leading-tight min-w-0">
                      <span style={{ color: T.ink }} className="block text-[11px] font-semibold truncate">{userLabel}</span>
                      <span style={{ color: T.sub }} className="block text-[10px]">Мой профиль</span>
                    </span>
                    <Check size={15} style={{ color: T.primary, marginLeft: "auto", flexShrink: 0 }} />
                  </div>
                  <button
                    onClick={async () => { await supabase.auth.signOut(); setAcctOpen(false); }}
                    style={{ color: "#c0392b" }}
                    className="w-full flex items-center gap-2 rounded-xl px-2 py-2 text-left text-[12px] font-semibold">
                    <LogOut size={14} />
                    Выйти
                  </button>
                </div>
              )}
            </div>

            {/* body */}
            <div onClick={() => acctOpen && setAcctOpen(false)}
              className="flex-1 overflow-y-auto scl px-5 pb-3">
              {tab === "create" && screen === "compose" && (
                <Compose
                  media={media}
                  onAddFile={handleAddFile}
                  onRemoveMedia={handleRemoveMedia}
                  caption={caption}
                  setCaption={setCaption}
                  sel={sel}
                  setSel={setSel}
                />
              )}
              {tab === "create" && screen === "publishing" && (
                <Publishing jobs={jobs} castId={castId} firstMedia={media[0]} />
              )}
              {tab === "create" && screen === "done" && (
                <Done jobs={jobs} onReset={handleReset} onGoAnalytics={() => setTab("analytics")} />
              )}
              {tab === "channels"  && <Channels />}
              {tab === "analytics" && <Analytics lastCastId={lastCastId} />}
            </div>

            {/* contextual footer */}
            {showFooter && (
              <div style={{ borderTop: `1px solid ${T.line}`, background: T.canvas }} className="px-5 py-3">
                {screen === "compose" && (
                  <>
                    <button disabled={!canPublish} onClick={handlePublish}
                      style={{ background: canPublish ? T.primary : "#c9c6bd", color: canPublish ? "#fff" : "#8d8a82" }}
                      className="w-full rounded-2xl py-3.5 font-bold text-[15px] flex items-center justify-center gap-2 transition-colors">
                      {uploadingAny ? "Загружаем файлы…" : "Опубликовать везде"} <ArrowRight size={18} />
                    </button>
                    {castError && (
                      <p style={{ color: "#c0392b" }} className="text-[11px] text-center mt-2">{castError}</p>
                    )}
                  </>
                )}
                {screen === "publishing" && (
                  <div style={{ color: T.sub }} className="text-[11.5px] text-center flex items-center justify-center gap-2 py-1">
                    <span style={{ background: T.live }} className="w-2 h-2 rounded-full" />
                    Публикуем на сервере — приложение можно закрыть
                  </div>
                )}
                {screen === "done" && (
                  <button onClick={handleReset}
                    style={{ background: T.ink, color: T.canvas }}
                    className="w-full rounded-2xl py-3.5 font-bold text-[15px] flex items-center justify-center gap-2">
                    <RotateCcw size={17} /> Новая сторис
                  </button>
                )}
              </div>
            )}

            {/* tab bar */}
            <div style={{ borderTop: `1px solid ${T.line}`, background: T.surface }} className="flex">
              {[
                { id: "create",    label: "Создать",   icon: Send },
                { id: "channels",  label: "Каналы",    icon: Link2 },
                { id: "analytics", label: "Аналитика", icon: BarChart3 },
              ].map((t) => {
                const on = tab === t.id;
                const Icon = t.icon;
                return (
                  <button key={t.id} onClick={() => setTab(t.id)}
                    className="flex-1 flex flex-col items-center gap-1 py-2.5">
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
