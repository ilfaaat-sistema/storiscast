import React, { useRef } from "react";
import { Plus, X, Image as ImageIcon, Video } from "lucide-react";
import { T, MONO, PLATFORMS } from "../tokens.js";
import { SectionLabel, Tag, AddTile } from "./Bits.jsx";

function DestRow({ p, on, nested, locked, onToggle }) {
  const fbOn = PLATFORMS.find((x) => x.id === "ig") && on;
  return (
    <div className="flex items-center gap-3 py-2.5 relative" style={{ paddingLeft: nested ? 22 : 0 }}>
      {nested && (
        <div style={{
          position: "absolute", left: 22, top: -2, width: 18, height: 22,
          borderLeft: `2px solid ${T.line}`, borderBottom: `2px solid ${T.line}`, borderBottomLeftRadius: 8,
        }} />
      )}
      <span style={{ background: on ? p.color : "#cfccc3", outline: `4px solid ${T.surface}` }}
        className="w-3.5 h-3.5 rounded-full shrink-0 z-10" />
      <div className="flex-1 leading-tight">
        <div style={{ color: on ? T.ink : T.sub }} className="text-[14px] font-semibold flex items-center gap-1.5">
          {p.name}
          {p.mode === "auto"   && <Tag>авто</Tag>}
          {p.mode === "manual" && <Tag>вручную</Tag>}
        </div>
        <div style={{ color: T.sub }} className="text-[10.5px] mt-0.5">{p.note}</div>
      </div>
      <button onClick={onToggle} disabled={locked}
        style={{ background: on ? p.color : "#cdc9c0", opacity: locked ? 0.5 : 1 }}
        className="w-[42px] h-[24px] rounded-full relative shrink-0 transition-colors"
        aria-label={`${p.name} ${on ? "включён" : "выключен"}`}>
        <span style={{ left: on ? 20 : 2 }} className="absolute top-[2px] w-5 h-5 rounded-full bg-white transition-all" />
      </button>
    </div>
  );
}

export default function Compose({ media, onAddFile, onRemoveMedia, caption, setCaption, sel, setSel }) {
  const fileRef = useRef(null);
  const pendingType = useRef("photo");
  const fbOn = sel.ig;

  const handleAddClick = (type) => {
    pendingType.current = type;
    fileRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) onAddFile(file, pendingType.current);
    e.target.value = "";
  };

  return (
    <div className="pt-1">
      <input ref={fileRef} type="file" accept="image/*,video/*" className="hidden" onChange={handleFileChange} />

      <SectionLabel n="01" title="Что публикуем" />
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 20 }}
        className="p-3 mb-2">
        {media.length === 0 ? (
          <div className="flex gap-2">
            <AddTile icon={<ImageIcon size={20} />} label="Фото" onClick={() => handleAddClick("photo")} />
            <AddTile icon={<Video size={20} />}     label="Видео" onClick={() => handleAddClick("video")} />
          </div>
        ) : (
          <div className="flex gap-2 overflow-x-auto scl">
            {media.map((m, i) => (
              <div key={m.id} className="relative shrink-0">
                <div style={{
                  width: 70, height: 96, borderRadius: 12,
                  background: m.preview
                    ? `url(${m.preview}) center/cover`
                    : `linear-gradient(150deg, hsl(${m.hue} 70% 62%), hsl(${(m.hue + 40) % 360} 65% 45%))`,
                }} className="flex items-end p-1.5">
                  {m.uploading && (
                    <span style={{ fontFamily: MONO }} className="text-white/80 text-[9px] font-bold">…</span>
                  )}
                  {!m.uploading && (
                    <span style={{ fontFamily: MONO }} className="text-white/90 text-[9px] font-bold flex items-center gap-0.5">
                      {m.type === "video" ? <Video size={11} /> : <ImageIcon size={11} />}{i + 1}
                    </span>
                  )}
                </div>
                <button onClick={() => onRemoveMedia(m.id)}
                  style={{ background: T.ink }}
                  className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full text-white flex items-center justify-center">
                  <X size={12} />
                </button>
              </div>
            ))}
            {media.length < 6 && (
              <button onClick={() => handleAddClick("photo")}
                style={{ width: 70, height: 96, border: `1.5px dashed ${T.line}`, color: T.sub, borderRadius: 12 }}
                className="shrink-0 flex flex-col items-center justify-center gap-1">
                <Plus size={18} /><span className="text-[10px] font-semibold">Ещё</span>
              </button>
            )}
          </div>
        )}
        <input value={caption} onChange={(e) => setCaption(e.target.value)}
          placeholder="Подпись (необязательно)…"
          style={{ color: T.ink, borderTop: media.length ? `1px solid ${T.line}` : "none" }}
          className="w-full bg-transparent outline-none text-[13.5px] mt-3 pt-3 placeholder:text-stone-400" />
      </div>

      <div className="mt-5"><SectionLabel n="02" title="Куда уходит" /></div>
      <div style={{ background: T.surface, border: `1px solid ${T.line}`, borderRadius: 20 }}
        className="px-3 py-1.5 mb-1 relative">
        <div style={{ position: "absolute", left: 22, top: 26, bottom: 26, width: 2, background: T.line }} />
        {PLATFORMS.map((p) => {
          const on = p.id === "fb" ? fbOn : !!sel[p.id];
          const nested = p.id === "fb";
          return (
            <DestRow key={p.id} p={p} on={on} nested={nested} locked={p.id === "fb"}
              onToggle={() => p.id !== "fb" && setSel((s) => ({ ...s, [p.id]: !s[p.id] }))} />
          );
        })}
      </div>
      <p style={{ color: T.sub }} className="text-[11px] leading-snug px-1 mt-2">
        Facebook подтянется автоматически вслед за Instagram. WhatsApp Status — ваш личный профиль, ставится вручную в один тап.
      </p>
    </div>
  );
}
