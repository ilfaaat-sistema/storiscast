import React, { useEffect, useState } from "react";
import { Check, Loader2, Info, DoorOpen } from "lucide-react";
import { T, MONO, PLATFORMS } from "../tokens.js";
import { SectionLabel, Tag } from "./Bits.jsx";
import { getAccounts, connectAccount } from "../api.js";

const STATIC_META = {
  fb: { state: "auto",   sub: "через Instagram" },
  wa: { state: "manual", sub: "Status · 24 ч" },
};

export default function Channels() {
  const [accounts, setAccounts] = useState([]);
  const [connecting, setConnecting] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    getAccounts().then(setAccounts).catch((e) => setError(e.message));
  }, []);

  const byPlatform = Object.fromEntries(accounts.map((a) => [a.platform, a]));

  const handleConnect = async (platformId) => {
    setConnecting((c) => ({ ...c, [platformId]: true }));
    try {
      const updated = await connectAccount(platformId);
      setAccounts((prev) => prev.map((a) => (a.platform === platformId ? updated : a)));
    } catch (e) {
      setError(e.message);
    } finally {
      setConnecting((c) => ({ ...c, [platformId]: false }));
    }
  };

  if (error) {
    return (
      <div className="pt-4 text-center" style={{ color: T.sub }}>
        <p className="text-[12px]">Ошибка загрузки: {error}</p>
      </div>
    );
  }

  return (
    <div className="pt-1">
      <SectionLabel n="✦" title="Подключённые каналы" />
      <div className="flex flex-col gap-2 mb-4">
        {PLATFORMS.map((p) => {
          const acc = byPlatform[p.id];
          const meta = STATIC_META[p.id];
          const status = meta?.state ?? (acc?.status ?? "off");
          const handle = acc?.handle ?? "";
          const sub = meta?.sub ?? (acc ? "подключён" : "не подключён");
          const isConnecting = connecting[p.id];

          return (
            <div key={p.id} style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 16 }}
              className="flex items-center gap-3 p-3">
              <span style={{ background: p.color }}
                className="w-9 h-9 rounded-full flex items-center justify-center text-white text-[13px] font-bold shrink-0">
                {p.name[0]}
              </span>
              <div className="flex-1 leading-tight min-w-0">
                <div style={{ color: T.ink }} className="text-[13.5px] font-semibold flex items-center gap-1.5">
                  {p.name}
                  {status === "auto"   && <Tag>авто</Tag>}
                  {status === "manual" && <Tag>вручную</Tag>}
                </div>
                <div style={{ color: T.sub, fontFamily: MONO }} className="text-[10.5px] mt-0.5 truncate">
                  {status === "off" ? "не подключён" : `${handle}${handle && sub ? " · " : ""}${sub}`}
                </div>
              </div>

              {isConnecting && <Loader2 size={16} className="spin shrink-0" style={{ color: T.primary }} />}
              {!isConnecting && (status === "connected" || status === "stub") && (
                <span style={{ color: T.ok, fontFamily: MONO }} className="text-[10px] uppercase flex items-center gap-1 shrink-0">
                  <Check size={13} /> подключён
                </span>
              )}
              {!isConnecting && status === "auto"   && <span style={{ color: T.sub, fontFamily: MONO }} className="text-[10px] uppercase shrink-0">прицепом</span>}
              {!isConnecting && status === "manual"  && <span style={{ color: p.color, fontFamily: MONO }} className="text-[10px] uppercase shrink-0">в 1 тап</span>}
              {!isConnecting && (status === "off" || status === "disconnected") && (
                <button onClick={() => handleConnect(p.id)} style={{ background: T.primary }}
                  className="text-white text-[11.5px] font-bold rounded-full px-3 py-1.5 shrink-0">
                  Подключить
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ background: "#fff7ed", border: "1px solid #f3d9b8", borderRadius: 16 }}
        className="p-3 flex gap-2.5">
        <Info size={16} style={{ color: T.live }} className="shrink-0 mt-0.5" />
        <div style={{ color: "#7a5320" }} className="text-[11.5px] leading-snug">
          <b>WhatsApp Status</b> — это истории на вашем <b>личном профиле</b> (живут 24 ч). Официального API нет, поэтому сервис открывает готовую историю, а вы публикуете её в один тап.
        </div>
      </div>

      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 16 }}
        className="p-3 flex gap-2.5 mt-2">
        <DoorOpen size={16} style={{ color: T.primary }} className="shrink-0 mt-0.5" />
        <div style={{ color: T.sub }} className="text-[11.5px] leading-snug">
          <b style={{ color: T.ink }}>Telegram</b> подключается по номеру и коду из приложения (личный профиль). Лимит без Premium — 3 истории в сутки; сервис ставит лишнее в очередь.
        </div>
      </div>
    </div>
  );
}
